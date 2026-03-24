package pt.tecnico.secure.model;

import java.util.List;

public class ProtectedDocument {
    public String ciphertext;
    public String iv;
    public List<WrappedKeyEntry> wrapped_keys;
    public SignaturesBlock signatures;
    public List<AccessEntry> access_list;
    public Metadata metadata;
    public Long timestamp;  // Unix timestamp in milliseconds for freshness
    public String nonce;    // Random nonce to prevent replay attacks
}
