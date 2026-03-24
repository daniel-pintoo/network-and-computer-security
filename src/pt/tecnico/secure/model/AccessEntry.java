package pt.tecnico.secure.model;

public class AccessEntry {
    public String recipient;
    public String wrapped_key;
    public String signed_by;
    public long timestamp;
    public String signature;
}
