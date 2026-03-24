package pt.tecnico.secure;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import java.security.*;
import java.security.spec.MGF1ParameterSpec;
import java.util.Base64;
import javax.crypto.spec.OAEPParameterSpec;
import javax.crypto.spec.PSource;
import java.security.spec.PSSParameterSpec;
import javax.crypto.spec.SecretKeySpec;

public class CryptoUtils {

    // AES-GCM
    public static SecretKey generateAESKey() throws Exception {
        KeyGenerator kg = KeyGenerator.getInstance("AES");
        kg.init(256);
        return kg.generateKey();
    }

    public static byte[] aesEncrypt(byte[] plaintext, SecretKey key, byte[] iv) throws Exception {
        Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
        GCMParameterSpec spec = new GCMParameterSpec(128, iv);
        c.init(Cipher.ENCRYPT_MODE, key, spec);
        return c.doFinal(plaintext);
    }

    public static byte[] aesDecrypt(byte[] ciphertext, SecretKey key, byte[] iv) throws Exception {
        Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
        GCMParameterSpec spec = new GCMParameterSpec(128, iv);
        c.init(Cipher.DECRYPT_MODE, key, spec);
        return c.doFinal(ciphertext);
    }

    // RSA-OAEP wrap / unwrap (try SHA-256 OAEP, fallback to default OAEP)
    public static byte[] rsaWrapKey(SecretKey key, PublicKey pub) throws Exception {
        try {
            Cipher c = Cipher.getInstance("RSA/ECB/OAEPWithSHA-256AndMGF1Padding");
            OAEPParameterSpec oaepParams = new OAEPParameterSpec(
                    "SHA-256",
                    "MGF1",
                    new MGF1ParameterSpec("SHA-256"),
                    PSource.PSpecified.DEFAULT);
            c.init(Cipher.WRAP_MODE, pub, oaepParams);
            return c.wrap(key);
        } catch (Exception e) {
            // fallback to provider default OAEP (likely SHA-1) if 256OAEP isn't available
            Cipher c = Cipher.getInstance("RSA/ECB/OAEPWithSHA-1AndMGF1Padding");
            c.init(Cipher.WRAP_MODE, pub);
            return c.wrap(key);
        }
    }

    public static SecretKey rsaUnwrapKey(byte[] wrapped, PrivateKey priv) throws Exception {
        try {
            Cipher c = Cipher.getInstance("RSA/ECB/OAEPWithSHA-256AndMGF1Padding");
            OAEPParameterSpec oaepParams = new OAEPParameterSpec(
                    "SHA-256",
                    "MGF1",
                    new MGF1ParameterSpec("SHA-256"),
                    PSource.PSpecified.DEFAULT);
            c.init(Cipher.UNWRAP_MODE, priv, oaepParams);
            return (SecretKey) c.unwrap(wrapped, "AES", Cipher.SECRET_KEY);
        } catch (Exception e) {
            Cipher c = Cipher.getInstance("RSA/ECB/OAEPWithSHA-1AndMGF1Padding");
            c.init(Cipher.UNWRAP_MODE, priv);
            return (SecretKey) c.unwrap(wrapped, "AES", Cipher.SECRET_KEY);
        }
    }

    // Sign (try RSASSA-PSS, fallback SHA256withRSA)
    public static byte[] sign(PrivateKey priv, byte[] data) throws Exception {
        try {
            Signature s = Signature.getInstance("RSASSA-PSS");
            PSSParameterSpec pss = new PSSParameterSpec("SHA-256", "MGF1",
                    MGF1ParameterSpec.SHA256, 32, 1);
            s.setParameter(pss);
            s.initSign(priv);
            s.update(data);
            return s.sign();
        } catch (Exception ex) {
            Signature s = Signature.getInstance("SHA256withRSA");
            s.initSign(priv);
            s.update(data);
            return s.sign();
        }
    }

    public static boolean verify(PublicKey pub, byte[] signature, byte[] data) throws Exception {
        try {
            Signature s = Signature.getInstance("RSASSA-PSS");
            PSSParameterSpec pss = new PSSParameterSpec("SHA-256", "MGF1",
                    MGF1ParameterSpec.SHA256, 32, 1);
            s.setParameter(pss);
            s.initVerify(pub);
            s.update(data);
            return s.verify(signature);
        } catch (Exception ex) {
            Signature s = Signature.getInstance("SHA256withRSA");
            s.initVerify(pub);
            s.update(data);
            return s.verify(signature);
        }
    }

    public static String b64(byte[] b) {
        return Base64.getEncoder().encodeToString(b);
    }

    public static byte[] ub64(String s) {
        return Base64.getDecoder().decode(s);
    }
}
