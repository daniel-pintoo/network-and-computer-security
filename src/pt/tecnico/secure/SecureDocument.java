package pt.tecnico.secure;

import pt.tecnico.secure.model.*;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.*;
import java.util.*;
import java.util.Base64;

public class SecureDocument {
    private static final Gson gson = new GsonBuilder().setPrettyPrinting().create();

    private static byte[] readAll(String path) throws Exception {
        return Files.readAllBytes(Paths.get(path));
    }

    public static void protect(String inputJsonPath,
                               PrivateKey sellerPriv,
                               List<PublicKey> recipients,
                               String outputPath) throws Exception {
        String[] defaultNames = {"Seller", "Buyer"};
        List<String> recipientNames = new ArrayList<>();
        for (int i = 0; i < recipients.size(); i++) {
            recipientNames.add(i < defaultNames.length ? defaultNames[i] : "recipient_" + UUID.randomUUID().toString().replace("-", "").substring(0,8));
        }
        protect(inputJsonPath, sellerPriv, recipients, recipientNames, outputPath);
    }

    public static void protect(String inputJsonPath,
                               PrivateKey sellerPriv,
                               List<PublicKey> recipients,
                               List<String> recipientNames,
                               String outputPath) throws Exception {

        if (recipients.size() != recipientNames.size()) {
            throw new Exception("Number of recipients must match number of recipient names");
        }

        byte[] plaintext = readAll(inputJsonPath);

        SecretKey aesKey = CryptoUtils.generateAESKey();
        byte[] iv = new byte[12];
        SecureRandom rnd = new SecureRandom();
        rnd.nextBytes(iv);

        byte[] ciphertext = CryptoUtils.aesEncrypt(plaintext, aesKey, iv);

        List<WrappedKeyEntry> wrapped = new ArrayList<>();
        for (int i = 0; i < recipients.size(); i++) {
            PublicKey pk = recipients.get(i);
            WrappedKeyEntry e = new WrappedKeyEntry();
            e.recipient = recipientNames.get(i);
            e.wrapped_key = Base64.getEncoder().encodeToString(CryptoUtils.rsaWrapKey(aesKey, pk));
            wrapped.add(e);
        }

        Metadata metadata = new Metadata();
        metadata.version = 1;
        try {
            String txt = new String(plaintext, "UTF-8");
            com.google.gson.JsonObject jo = com.google.gson.JsonParser.parseString(txt).getAsJsonObject();
            if (jo.has("id")) metadata.transaction_id = jo.get("id").getAsInt();
        } catch (Exception ignore) {}

        ProtectedDocument doc = new ProtectedDocument();
        doc.ciphertext = Base64.getEncoder().encodeToString(ciphertext);
        doc.iv = Base64.getEncoder().encodeToString(iv);
        doc.wrapped_keys = wrapped;
        doc.metadata = metadata;
        doc.access_list = new ArrayList<>();
        
        doc.timestamp = System.currentTimeMillis();
        byte[] nonceBytes = new byte[16];
        rnd.nextBytes(nonceBytes);
        doc.nonce = Base64.getEncoder().encodeToString(nonceBytes);

        Map<String,Object> signObj = new TreeMap<>();
        signObj.put("ciphertext", doc.ciphertext);
        signObj.put("iv", doc.iv);
        signObj.put("metadata", doc.metadata);
        signObj.put("timestamp", doc.timestamp);
        signObj.put("nonce", doc.nonce);
        byte[] toSign = gson.toJson(signObj).getBytes("UTF-8");

        doc.signatures = new SignaturesBlock();
        doc.signatures.seller_signature = CryptoUtils.b64(CryptoUtils.sign(sellerPriv, toSign));

        Files.write(Paths.get(outputPath), gson.toJson(doc).getBytes("UTF-8"));
        System.out.println("Protected written to " + outputPath);
    }

    public static void unprotect(String protectedPath, PrivateKey recipientPriv, String outPath) throws Exception {
        String json = new String(readAll(protectedPath), "UTF-8");
        ProtectedDocument doc = gson.fromJson(json, ProtectedDocument.class);

        SecretKey found = null;
        for (WrappedKeyEntry e : doc.wrapped_keys) {
            byte[] wrapped = Base64.getDecoder().decode(e.wrapped_key);
            try {
                found = CryptoUtils.rsaUnwrapKey(wrapped, recipientPriv);
                break;
            } catch (Exception ex) {
                
            }
        }
        if (found == null && doc.access_list != null) {
            for (AccessEntry ae : doc.access_list) {
                byte[] wrapped = Base64.getDecoder().decode(ae.wrapped_key);
                try {
                    found = CryptoUtils.rsaUnwrapKey(wrapped, recipientPriv);
                    break;
                } catch (Exception ex) {
                }
            }
        }
        if (found == null) throw new Exception("No wrapped key could be unwrapped with provided private key.");

        byte[] ciphertext = Base64.getDecoder().decode(doc.ciphertext);
        byte[] iv = Base64.getDecoder().decode(doc.iv);

        byte[] plaintext = CryptoUtils.aesDecrypt(ciphertext, found, iv);
        Files.write(Paths.get(outPath), plaintext);
        System.out.println("Decrypted and saved to " + outPath);
    }

    public static Map<String, Object> check(String protectedPath, PublicKey sellerPub) throws Exception {
        String json = new String(readAll(protectedPath), "UTF-8");
        ProtectedDocument doc = gson.fromJson(json, ProtectedDocument.class);

        Map<String,Object> result = new HashMap<>();

        boolean isFresh = (doc.timestamp != null && doc.nonce != null && !doc.nonce.isEmpty());
        result.put("is_fresh", isFresh);

        Map<String,Object> signObj = new TreeMap<>();
        signObj.put("ciphertext", doc.ciphertext);
        signObj.put("iv", doc.iv);
        signObj.put("metadata", doc.metadata);
        signObj.put("timestamp", doc.timestamp);
        signObj.put("nonce", doc.nonce);
        byte[] toVerify = gson.toJson(signObj).getBytes("UTF-8");

        boolean sellerOK = CryptoUtils.verify(sellerPub, Base64.getDecoder().decode(doc.signatures.seller_signature), toVerify);

        boolean accessOk = true;
        List<Map<String,Object>> accessDetails = new ArrayList<>();
        if (doc.access_list != null) {
            for (AccessEntry ae : doc.access_list) {
                Map<String,Object> entryMap = new HashMap<>();
                entryMap.put("entry", ae);
                PublicKey signerPub = null;
                if (ae.signed_by != null && ae.signed_by.toLowerCase().startsWith("seller")) signerPub = sellerPub;
                boolean ok = false;
                if (signerPub != null) {
                    Map<String,Object> toSign = new TreeMap<>();
                    toSign.put("recipient", ae.recipient);
                    toSign.put("wrapped_key", ae.wrapped_key);
                    toSign.put("signed_by", ae.signed_by);
                    toSign.put("timestamp", ae.timestamp);
                    byte[] tb = gson.toJson(toSign).getBytes("UTF-8");
                    ok = CryptoUtils.verify(signerPub, Base64.getDecoder().decode(ae.signature), tb);
                }
                entryMap.put("ok", ok);
                accessDetails.add(entryMap);
                if (!ok) accessOk = false;
            }
        }

        result.put("seller_signature_ok", sellerOK);
        result.put("access_list_ok", accessOk);
        result.put("access_list_details", accessDetails);
        return result;
    }

    /**
     * Share a protected document with a new recipient.
     * Anyone with a wrapped_key in the document can share (SR2: Authentication).
     * The sharer must be able to unwrap one of the keys to prove they have access.
     * Creates a signed access entry (SR4: Integrity of sharing history).
     * 
     * @param protectedPath Path to the protected document
     * @param newRecipientPub Public key of the new recipient
     * @param newRecipientName Name/identifier of the new recipient
     * @param sharerPriv Private key of the sharer (Seller or Buyer)
     * @param sharerName Name of the sharer (e.g., "Seller", "Buyer", or recipient name)
     * @param outputPath Path to save the updated document
     */
    public static void share(String protectedPath, 
                            PublicKey newRecipientPub,
                            String newRecipientName,
                            PrivateKey sharerPriv, 
                            String sharerName,
                            String outputPath) throws Exception {
        
        String json = new String(readAll(protectedPath), "UTF-8");
        ProtectedDocument doc = gson.fromJson(json, ProtectedDocument.class);

        SecretKey aesKey = null;
        for (WrappedKeyEntry e : doc.wrapped_keys) {
            try {
                byte[] wrapped = Base64.getDecoder().decode(e.wrapped_key);
                aesKey = CryptoUtils.rsaUnwrapKey(wrapped, sharerPriv);
                break;
            } catch (Exception ex) {
            }
        }
        if (aesKey == null && doc.access_list != null) {
            for (AccessEntry ae : doc.access_list) {
                try {
                    byte[] wrapped = Base64.getDecoder().decode(ae.wrapped_key);
                    aesKey = CryptoUtils.rsaUnwrapKey(wrapped, sharerPriv);
                    break;
                } catch (Exception ex) {
                }
            }
        }
        if (aesKey == null) {
            throw new Exception("Cannot unwrap AES key - sharer does not have access");
        }

        byte[] wrappedForRecipient = CryptoUtils.rsaWrapKey(aesKey, newRecipientPub);
        String wrappedKeyB64 = Base64.getEncoder().encodeToString(wrappedForRecipient);

        AccessEntry entry = new AccessEntry();
        entry.recipient = newRecipientName;
        entry.wrapped_key = wrappedKeyB64;
        entry.signed_by = sharerName;
        entry.timestamp = System.currentTimeMillis();

        Map<String,Object> toSign = new TreeMap<>();
        toSign.put("recipient", entry.recipient);
        toSign.put("wrapped_key", entry.wrapped_key);
        toSign.put("signed_by", entry.signed_by);
        toSign.put("timestamp", entry.timestamp);
        byte[] signatureBytes = CryptoUtils.sign(sharerPriv, gson.toJson(toSign).getBytes("UTF-8"));
        entry.signature = Base64.getEncoder().encodeToString(signatureBytes);

        if (doc.access_list == null) {
            doc.access_list = new ArrayList<>();
        }
        doc.access_list.add(entry);

        Files.write(Paths.get(outputPath), gson.toJson(doc).getBytes("UTF-8"));
        System.out.println("Document shared with " + newRecipientName);
        System.out.println("Updated document written to " + outputPath);
    }
}
