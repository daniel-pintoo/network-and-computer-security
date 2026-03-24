package pt.tecnico.secure;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.*;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

public class SecureDocumentAPI {
    private static final Gson gson = new GsonBuilder().setPrettyPrinting().create();

    public static void main(String[] args) {
        try {
            if (args.length < 1) {
                System.err.println("Usage: SecureDocumentAPI <command> [arguments]");
                System.exit(1);
            }
            
            String command = args[0].toLowerCase();
            
            switch (command) {
                case "checkjson":
                    if (args.length != 3) {
                        System.err.println("Error: checkJson requires 2 arguments");
                        System.err.println("Usage: SecureDocumentAPI checkJson <protected-path> <seller-pub-path>");
                        System.exit(1);
                    }
                    checkJson(args[1], args[2]);
                    break;
                case "protectjson":
                    if (args.length != 8) {
                        System.err.println("Error: protectJson requires 7 arguments");
                        System.err.println("Usage: SecureDocumentAPI protectJson <input-path> <seller-priv-path> <seller-pub-path> <buyer-pub-path> <seller-name> <buyer-name> <output-path>");
                        System.exit(1);
                    }
                    protectJson(args[1], args[2], args[3], args[4], args[5], args[6], args[7]);
                    break;
                default:
                    System.err.println("Error: Unknown command '" + command + "'");
                    System.exit(1);
            }
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }

    /**
     * Check document and return JSON result.
     */
    public static void checkJson(String protectedPath, String sellerPubPath) throws Exception {
        PublicKey sellerPub = loadPublicKey(sellerPubPath);
        
        Map<String, Object> result = SecureDocument.check(protectedPath, sellerPub);
        
        // Output JSON to stdout (without pretty printing for API use)
        Gson compactGson = new GsonBuilder().create();
        System.out.println(compactGson.toJson(result));
    }

    /**
     * Helper method to load public key.
     */
    public static PublicKey loadPublicKey(String path) throws Exception {
        byte[] keyBytes = Files.readAllBytes(Paths.get(path));
        X509EncodedKeySpec spec = new X509EncodedKeySpec(keyBytes);
        KeyFactory kf = KeyFactory.getInstance("RSA");
        return kf.generatePublic(spec);
    }

    /**
     * Helper method to load private key.
     */
    public static PrivateKey loadPrivateKey(String path) throws Exception {
        byte[] keyBytes = Files.readAllBytes(Paths.get(path));
        PKCS8EncodedKeySpec spec = new PKCS8EncodedKeySpec(keyBytes);
        KeyFactory kf = KeyFactory.getInstance("RSA");
        return kf.generatePrivate(spec);
    }

    public static void protectJson(String inputPath, String sellerPrivPath, String sellerPubPath, 
                                    String buyerPubPath, String sellerName, String buyerName, 
                                    String outputPath) throws Exception {
        PrivateKey sellerPriv = loadPrivateKey(sellerPrivPath);
        PublicKey sellerPub = loadPublicKey(sellerPubPath);
        PublicKey buyerPub = loadPublicKey(buyerPubPath);
        
        List<PublicKey> recipients = Arrays.asList(sellerPub, buyerPub);
        List<String> recipientNames = Arrays.asList(sellerName, buyerName);
        
        SecureDocument.protect(inputPath, sellerPriv, recipients, recipientNames, outputPath);
        
        System.out.println("Protected document written to " + outputPath);
    }
}

