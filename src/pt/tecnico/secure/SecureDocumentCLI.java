package pt.tecnico.secure;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.FileReader;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.*;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.*;

public class SecureDocumentCLI {
    private static final Gson gson = new GsonBuilder().setPrettyPrinting().create();

    public static void main(String[] args) {
        try {
            if (args.length == 0) {
                printUsage();
                System.exit(1);
            }

            String command = args[0].toLowerCase();

            switch (command) {
                case "help":
                    printHelp();
                    break;
                case "protect":
                    protect(args);
                    break;
                case "check":
                    check(args);
                    break;
                case "unprotect":
                    unprotect(args);
                    break;
                case "share":
                    share(args);
                    break;
                default:
                    System.err.println("Error: Unknown command '" + command + "'");
                    System.err.println();
                    printUsage();
                    System.exit(1);
            }
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            if (e.getCause() != null) {
                System.err.println("Details: " + e.getCause().getMessage());
            }
            e.printStackTrace();
            System.exit(1);
        }
    }

    private static void printUsage() {
        System.out.println("Usage: secure-docs <command> [arguments]");
        System.out.println();
        System.out.println("Commands:");
        System.out.println("  help                                          Show detailed help");
        System.out.println("  protect <input> <seller-priv> <seller-pub> <buyer-pub> <output>");
        System.out.println("  check <input> <seller-pub>");
        System.out.println("  unprotect <input> <recipient-priv> <output>");
        System.out.println("  share <protected> <new-recip-pub> <new-recip-name> <sharer-priv> <sharer-name> <output>");
        System.out.println();
        System.out.println("Run 'secure-docs help' for more information.");
    }

    private static void printHelp() {
        System.out.println("Secure Documents - Cryptographic Document Protection Tool");
        System.out.println("==========================================================");
        System.out.println();
        System.out.println("COMMANDS:");
        System.out.println();
        System.out.println("  help");
        System.out.println("    Display this help message with detailed information about all commands.");
        System.out.println();
        System.out.println("  protect <input-file> <seller-private-key> <seller-public-key> <buyer-public-key> <output-file>");
        System.out.println("    Protect a JSON document with encryption, integrity, and freshness protection.");
        System.out.println("    Called by seller only. Seller signs the document.");
        System.out.println("    Seller and buyer public keys are used to create wrapped keys so both can decrypt.");
        System.out.println("    ");
        System.out.println("    Arguments:");
        System.out.println("      <input-file>          - Path to the plaintext JSON document");
        System.out.println("      <seller-private-key>  - Path to seller's private key (for signing)");
        System.out.println("      <seller-public-key>   - Path to seller's public key (for key wrapping)");
        System.out.println("      <buyer-public-key>    - Path to buyer's public key (for key wrapping)");
        System.out.println("      <output-file>         - Path where protected document will be saved");
        System.out.println();
        System.out.println("    Security features:");
        System.out.println("      - Confidentiality: AES-256-GCM encryption");
        System.out.println("      - Integrity: RSA digital signature from seller");
        System.out.println("      - Freshness: Timestamp and nonce to prevent replay attacks");
        System.out.println();
        System.out.println("  check <input-file> <seller-public-key>");
        System.out.println("    Verify the integrity and freshness of a protected document.");
        System.out.println("    ");
        System.out.println("    Arguments:");
        System.out.println("      <input-file>        - Path to the protected JSON document");
        System.out.println("      <seller-public-key> - Path to seller's public key (for signature verification)");
        System.out.println();
        System.out.println("    Returns:");
        System.out.println("      - Freshness status (timestamp and nonce validation)");
        System.out.println("      - Seller signature verification result");
        System.out.println("      - Access list integrity (if present)");
        System.out.println();
        System.out.println("  unprotect <input-file> <recipient-private-key> <output-file>");
        System.out.println("    Decrypt a protected document and save the plaintext.");
        System.out.println("    ");
        System.out.println("    Arguments:");
        System.out.println("      <input-file>            - Path to the protected JSON document");
        System.out.println("      <recipient-private-key> - Path to recipient's private key (for unwrapping)");
        System.out.println("      <output-file>           - Path where decrypted document will be saved");
        System.out.println();
        System.out.println("  share <protected-file> <new-recipient-public-key> <new-recipient-name> <sharer-private-key> <sharer-name> <output-file>");
        System.out.println("    Share a protected document with a new recipient (SR2: Only seller/buyer can share).");
        System.out.println("    Creates a signed access entry for audit trail (SR4: Integrity of sharing history).");
        System.out.println("    ");
        System.out.println("    Arguments:");
        System.out.println("      <protected-file>           - Path to the protected JSON document");
        System.out.println("      <new-recipient-public-key> - Path to new recipient's public key");
        System.out.println("      <new-recipient-name>       - Name/identifier of new recipient (e.g., 'CompanyA')");
        System.out.println("      <sharer-private-key>       - Path to sharer's private key (seller or buyer)");
        System.out.println("      <sharer-name>              - Name of sharer ('Seller' or 'Buyer')");
        System.out.println("      <output-file>              - Path where updated document will be saved");
        System.out.println();
        System.out.println("KEY FORMAT:");
        System.out.println("  All keys must be in DER format (binary).");
        System.out.println("  - Private keys: PKCS#8 format");
        System.out.println("  - Public keys: X.509 SubjectPublicKeyInfo format");
        System.out.println();
        System.out.println("EXAMPLES:");
        System.out.println("  # Protect a document");
        System.out.println("  secure-docs protect transaction.json keys/seller-priv.key \\");
        System.out.println("                      keys/seller-pub.key keys/buyer-pub.key transaction-protected.json");
        System.out.println();
        System.out.println("  # Check document integrity");
        System.out.println("  secure-docs check transaction-protected.json keys/seller-pub.key");
        System.out.println();
        System.out.println("  # Decrypt document");
        System.out.println("  secure-docs unprotect transaction-protected.json keys/seller-priv.key transaction-decrypted.json");
        System.out.println();
        System.out.println("  # Share document with third party");
        System.out.println("  secure-docs share transaction-protected.json keys/companyA-pub.key CompanyA \\");
        System.out.println("                    keys/seller-priv.key Seller transaction-shared.json");
        System.out.println();
    }

    private static void protect(String[] args) throws Exception {
        if (args.length != 6) {
            System.err.println("Error: 'protect' command requires 5 arguments");
            System.err.println();
            System.err.println("Usage: secure-docs protect <input-file> <seller-private-key> <seller-public-key> <buyer-public-key> <output-file>");
            System.err.println();
            System.err.println("Run 'secure-docs help' for more information.");
            System.exit(1);
        }

        String inputFile = args[1];
        String sellerPrivFile = args[2];
        String sellerPubFile = args[3];
        String buyerPubFile = args[4];
        String outputFile = args[5];

        // Validate input files exist
        validateFileExists(inputFile, "Input file");
        validateFileExists(sellerPrivFile, "Seller private key");
        validateFileExists(sellerPubFile, "Seller public key");
        validateFileExists(buyerPubFile, "Buyer public key");

        System.out.println("Loading keys...");
        PrivateKey sellerPriv = loadPrivateKey(sellerPrivFile);
        PublicKey sellerPub = loadPublicKey(sellerPubFile);
        PublicKey buyerPub = loadPublicKey(buyerPubFile);

        List<PublicKey> recipients = Arrays.asList(sellerPub, buyerPub);

        System.out.println("Protecting document...");
        SecureDocument.protect(inputFile, sellerPriv, recipients, outputFile);
        
        System.out.println();
        System.out.println("✓ Document successfully protected");
        System.out.println("  Output: " + outputFile);
    }

    private static void check(String[] args) throws Exception {
        if (args.length != 3) {
            System.err.println("Error: 'check' command requires 2 arguments");
            System.err.println();
            System.err.println("Usage: secure-docs check <input-file> <seller-public-key>");
            System.err.println();
            System.err.println("Run 'secure-docs help' for more information.");
            System.exit(1);
        }

        String inputFile = args[1];
        String sellerPubFile = args[2];

        validateFileExists(inputFile, "Input file");
        validateFileExists(sellerPubFile, "Seller public key");

        System.out.println("Loading keys...");
        PublicKey sellerPub = loadPublicKey(sellerPubFile);

        System.out.println("Checking document...");
        Map<String, Object> result = SecureDocument.check(inputFile, sellerPub);

        System.out.println();
        System.out.println("VERIFICATION RESULTS:");
        System.out.println("====================");
        
        boolean isFresh = (Boolean) result.get("is_fresh");
        System.out.println("Freshness:         " + (isFresh ? "✓ VALID" : "✗ INVALID"));
        
        boolean sellerOK = (Boolean) result.get("seller_signature_ok");
        System.out.println("Seller Signature:  " + (sellerOK ? "✓ VALID" : "✗ INVALID"));
        
        boolean accessOK = (Boolean) result.get("access_list_ok");
        System.out.println("Access List:       " + (accessOK ? "✓ VALID" : "✗ INVALID"));

        System.out.println();
        if (isFresh && sellerOK && accessOK) {
            System.out.println("✓ Document is VALID and SECURE");
        } else {
            System.out.println("✗ Document verification FAILED");
            System.exit(1);
        }
    }

    private static void unprotect(String[] args) throws Exception {
        if (args.length != 4) {
            System.err.println("Error: 'unprotect' command requires 3 arguments");
            System.err.println();
            System.err.println("Usage: secure-docs unprotect <input-file> <recipient-private-key> <output-file>");
            System.err.println();
            System.err.println("Run 'secure-docs help' for more information.");
            System.exit(1);
        }

        String inputFile = args[1];
        String recipientPrivFile = args[2];
        String outputFile = args[3];

        validateFileExists(inputFile, "Input file");
        validateFileExists(recipientPrivFile, "Recipient private key");

        System.out.println("Loading key...");
        PrivateKey recipientPriv = loadPrivateKey(recipientPrivFile);

        System.out.println("Decrypting document...");
        SecureDocument.unprotect(inputFile, recipientPriv, outputFile);

        System.out.println();
        System.out.println("✓ Document successfully decrypted");
        System.out.println("  Output: " + outputFile);
    }

    private static void share(String[] args) throws Exception {
        if (args.length != 7) {
            System.err.println("Error: 'share' command requires 6 arguments");
            System.err.println();
            System.err.println("Usage: secure-docs share <protected-file> <new-recipient-public-key> <new-recipient-name> <sharer-private-key> <sharer-name> <output-file>");
            System.err.println();
            System.err.println("Run 'secure-docs help' for more information.");
            System.exit(1);
        }

        String protectedFile = args[1];
        String newRecipientPubFile = args[2];
        String newRecipientName = args[3];
        String sharerPrivFile = args[4];
        String sharerName = args[5];
        String outputFile = args[6];

        validateFileExists(protectedFile, "Protected document");
        validateFileExists(newRecipientPubFile, "New recipient public key");
        validateFileExists(sharerPrivFile, "Sharer private key");

        System.out.println("Loading keys...");
        PublicKey newRecipientPub = loadPublicKey(newRecipientPubFile);
        PrivateKey sharerPriv = loadPrivateKey(sharerPrivFile);

        System.out.println("Sharing document with " + newRecipientName + "...");
        SecureDocument.share(protectedFile, newRecipientPub, newRecipientName, sharerPriv, sharerName, outputFile);

        System.out.println();
        System.out.println("✓ Document successfully shared");
        System.out.println("  Shared with: " + newRecipientName);
        System.out.println("  Shared by: " + sharerName);
        System.out.println("  Output: " + outputFile);
    }

    private static void validateFileExists(String path, String description) throws Exception {
        if (!Files.exists(Paths.get(path))) {
            throw new Exception(description + " not found: " + path);
        }
    }

    private static PrivateKey loadPrivateKey(String path) throws Exception {
        byte[] keyBytes = Files.readAllBytes(Paths.get(path));
        PKCS8EncodedKeySpec spec = new PKCS8EncodedKeySpec(keyBytes);
        KeyFactory kf = KeyFactory.getInstance("RSA");
        return kf.generatePrivate(spec);
    }

    private static PublicKey loadPublicKey(String path) throws Exception {
        byte[] keyBytes = Files.readAllBytes(Paths.get(path));
        X509EncodedKeySpec spec = new X509EncodedKeySpec(keyBytes);
        KeyFactory kf = KeyFactory.getInstance("RSA");
        return kf.generatePublic(spec);
    }
}
