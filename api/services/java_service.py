"""
Service layer for interacting with Java SecureDocument CLI.
This separates the Java logic from the API layer.
"""
import subprocess
import os
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class JavaSecureDocumentService:
    """Service to interact with Java SecureDocument CLI."""
    
    def __init__(self, java_classpath: Optional[str] = None, java_main_class: str = "pt.tecnico.secure.SecureDocumentCLI"):
        """
        Initialize the service.
        
        Args:
            java_classpath: Path to compiled Java classes or JAR file
            java_main_class: Main class to execute
        """
        self.java_main_class = java_main_class
        self.java_classpath = java_classpath or self._find_classpath()
        self.temp_dir = Path(tempfile.gettempdir()) / "secure_docs_api"
        self.temp_dir.mkdir(exist_ok=True)
    
    def _find_classpath(self) -> str:
        """Try to find the Java classpath automatically, including Maven dependencies."""
        import subprocess
        
        # Get the project root by finding pom.xml
        # Start from this file's location and go up until we find pom.xml
        current = Path(__file__).parent  # api/services/
        project_root = current.parent.parent  # Go up to project root
        
        # Verify we found the project root by checking for pom.xml
        if not (project_root / "pom.xml").exists():
            # Try alternative: look from current working directory
            cwd = Path.cwd()
            if (cwd / "pom.xml").exists():
                project_root = cwd
            elif (cwd.parent / "pom.xml").exists():
                project_root = cwd.parent
            else:
                # Fallback: assume we're in project root
                project_root = Path.cwd()
        
        # Check for Maven target directory
        target_dir = project_root / "target" / "classes"
        if not target_dir.exists():
            # Default to current directory if target/classes doesn't exist
            return "."
        
        # Build classpath with Maven dependencies
        classpath_parts = [str(target_dir.absolute())]
        
        # Try to get Maven dependencies classpath
        maven_classpath = None
        try:
            # Change to project root to run Maven command
            result = subprocess.run(
                ["mvn", "dependency:build-classpath", "-q", "-DincludeScope=compile"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                maven_classpath = result.stdout.strip()
                classpath_parts.append(maven_classpath)
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            # If Maven command fails, try to find dependencies manually
            # Maven dependencies are typically in ~/.m2/repository
            pass
        
        # Fallback: try to find dependencies manually if Maven command failed
        if not maven_classpath:
            m2_repo = Path.home() / ".m2" / "repository"
            manual_classpath = self._find_maven_deps_manual(m2_repo)
            if manual_classpath:
                classpath_parts.append(manual_classpath)
        
        # Join classpath parts (use : on Unix, ; on Windows)
        separator = ":" if os.name != "nt" else ";"
        return separator.join(classpath_parts)
    
    def _find_maven_deps_manual(self, m2_repo: Path) -> str:
        """Manually find Maven dependencies for this project."""
        # This is a fallback - try to find Gson and other dependencies
        # Based on pom.xml: com.google.code.gson:gson:2.10.1
        deps = []
        
        gson_path = m2_repo / "com" / "google" / "code" / "gson" / "gson" / "2.10.1" / "gson-2.10.1.jar"
        if gson_path.exists():
            deps.append(str(gson_path))
        
        # Add other dependencies if needed
        jaxb_api = m2_repo / "javax" / "xml" / "bind" / "jaxb-api" / "2.3.0" / "jaxb-api-2.3.0.jar"
        if jaxb_api.exists():
            deps.append(str(jaxb_api))
        
        jaxb_core = m2_repo / "com" / "sun" / "xml" / "bind" / "jaxb-core" / "2.3.0" / "jaxb-core-2.3.0.jar"
        if jaxb_core.exists():
            deps.append(str(jaxb_core))
        
        jaxb_impl = m2_repo / "com" / "sun" / "xml" / "bind" / "jaxb-impl" / "2.3.0" / "jaxb-impl-2.3.0.jar"
        if jaxb_impl.exists():
            deps.append(str(jaxb_impl))
        
        annotation_api = m2_repo / "javax" / "annotation" / "javax.annotation-api" / "1.3.2" / "javax.annotation-api-1.3.2.jar"
        if annotation_api.exists():
            deps.append(str(annotation_api))
        
        separator = ":" if os.name != "nt" else ";"
        return separator.join(deps) if deps else ""
    
    def _run_java_command_with_class(self, java_class: str, args: list) -> Tuple[bool, str, str]:
        """
        Run a Java command with a specific class and return the result.
        
        Args:
            java_class: The Java class to run
            args: List of arguments for the command
        
        Returns:
            Tuple of (success, stdout, stderr)
        """
        # Build command
        cmd = [
            "java",
            "-cp", self.java_classpath,
            java_class
        ] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def _run_java_command(self, command: str, args: list, input_files: Dict[str, bytes] = None) -> Tuple[bool, str, str]:
        """
        Run a Java command and return the result.
        
        Args:
            command: The command to run (protect, check, unprotect, share)
            args: List of arguments for the command
            input_files: Dictionary of file paths to file contents (bytes)
        
        Returns:
            Tuple of (success, stdout, stderr)
        """
        # Write input files to temp directory
        file_paths = []
        if input_files:
            for file_path, content in input_files.items():
                temp_file = self.temp_dir / f"{os.urandom(8).hex()}_{Path(file_path).name}"
                temp_file.write_bytes(content)
                file_paths.append(str(temp_file))
        
        # Build command
        cmd = [
            "java",
            "-cp", self.java_classpath,
            self.java_main_class,
            command
        ] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
        finally:
            # Clean up temp files
            for file_path in file_paths:
                try:
                    os.remove(file_path)
                except:
                    pass
    
    def protect(
        self,
        input_document: bytes,
        seller_priv_key: bytes,
        seller_pub_key: bytes,
        buyer_pub_key: bytes,
        seller_name: str,
        buyer_name: str
    ) -> Tuple[bool, Optional[bytes], str]:
        """
        Protect a document.
        
        Args:
            input_document: Plaintext document bytes
            seller_priv_key: Seller's private key bytes (for signing)
            seller_pub_key: Seller's public key bytes (for key wrapping)
            buyer_pub_key: Buyer's public key bytes (for key wrapping)
            seller_name: Seller's name (CN from certificate)
            buyer_name: Buyer's name (CN from certificate)
        
        Returns:
            Tuple of (success, protected_document_bytes, error_message)
        """
        # Create temp files
        temp_input = self.temp_dir / f"{os.urandom(8).hex()}_input.json"
        temp_seller_priv = self.temp_dir / f"{os.urandom(8).hex()}_seller_priv.key"
        temp_seller_pub = self.temp_dir / f"{os.urandom(8).hex()}_seller_pub.key"
        temp_buyer_pub = self.temp_dir / f"{os.urandom(8).hex()}_buyer_pub.key"
        temp_output = self.temp_dir / f"{os.urandom(8).hex()}_output.json"
        
        try:
            # Write input files
            temp_input.write_bytes(input_document)
            temp_seller_priv.write_bytes(seller_priv_key)
            temp_seller_pub.write_bytes(seller_pub_key)
            temp_buyer_pub.write_bytes(buyer_pub_key)
            
            # Use SecureDocumentAPI with recipient names
            args = [
                "protectJson",
                str(temp_input),
                str(temp_seller_priv),
                str(temp_seller_pub),
                str(temp_buyer_pub),
                seller_name,
                buyer_name,
                str(temp_output)
            ]
            
            # Use SecureDocumentAPI instead of SecureDocumentCLI
            success, stdout, stderr = self._run_java_command_with_class(
                "pt.tecnico.secure.SecureDocumentAPI", args
            )
            
            if success and temp_output.exists():
                protected_doc = temp_output.read_bytes()
                return True, protected_doc, stdout
            else:
                return False, None, stderr or stdout
        
        finally:
            # Clean up
            for f in [temp_input, temp_seller_priv, temp_seller_pub, temp_buyer_pub, temp_output]:
                try:
                    if f.exists():
                        f.unlink()
                except:
                    pass
    
    def check(
        self,
        protected_document: bytes,
        seller_pub_key: bytes
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Check document integrity.
        
        Returns:
            Tuple of (success, result_dict, error_message)
        """
        temp_input = self.temp_dir / f"{os.urandom(8).hex()}_protected.json"
        temp_seller_pub = self.temp_dir / f"{os.urandom(8).hex()}_seller_pub.key"
        
        try:
            temp_input.write_bytes(protected_document)
            temp_seller_pub.write_bytes(seller_pub_key)
            
            # Try using SecureDocumentAPI first (JSON output)
            args = [
                str(temp_input),
                str(temp_seller_pub)
            ]
            
            cmd = [
                "java",
                "-cp", self.java_classpath,
                "pt.tecnico.secure.SecureDocumentAPI",
                "checkJson"
            ] + args
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    # Parse JSON output
                    result_dict = json.loads(result.stdout.strip())
                    return True, result_dict, ""
                else:
                    # Fallback to CLI parsing
                    pass
            except (json.JSONDecodeError, FileNotFoundError):
                # Fallback to CLI if API class doesn't exist or JSON parsing fails
                pass
            
            # Fallback: Use CLI and parse output
            success, stdout, stderr = self._run_java_command("check", args)
            
            if success:
                # Parse the output to extract verification results
                output_lines = stdout.split('\n')
                result = {
                    "is_fresh": False,
                    "seller_signature_ok": False,
                    "access_list_ok": False,
                    "raw_output": stdout
                }
                
                for line in output_lines:
                    if "Freshness:" in line:
                        result["is_fresh"] = "✓ VALID" in line or "VALID" in line
                    elif "Seller Signature:" in line:
                        result["seller_signature_ok"] = "✓ VALID" in line or "VALID" in line
                    elif "Access List:" in line:
                        result["access_list_ok"] = "✓ VALID" in line or "VALID" in line
                
                return True, result, ""
            else:
                # If command failed, it might be because verification failed
                if "verification FAILED" in stdout or "FAILED" in stdout:
                    # Parse partial results even on failure
                    output_lines = stdout.split('\n')
                    result = {
                        "is_fresh": False,
                        "seller_signature_ok": False,
                        "access_list_ok": False,
                        "raw_output": stdout
                    }
                    
                    for line in output_lines:
                        if "Freshness:" in line:
                            result["is_fresh"] = "✓ VALID" in line or "VALID" in line
                        elif "Seller Signature:" in line:
                            result["seller_signature_ok"] = "✓ VALID" in line or "VALID" in line
                        elif "Access List:" in line:
                            result["access_list_ok"] = "✓ VALID" in line or "VALID" in line
                    
                    return True, result, ""  # Return results even if verification failed
                else:
                    return False, None, stderr or stdout
        
        finally:
            for f in [temp_input, temp_seller_pub]:
                try:
                    if f.exists():
                        f.unlink()
                except:
                    pass
    
    def unprotect(
        self,
        protected_document: bytes,
        recipient_priv_key: bytes
    ) -> Tuple[bool, Optional[bytes], str]:
        """
        Unprotect (decrypt) a document.
        
        Returns:
            Tuple of (success, decrypted_document_bytes, error_message)
        """
        temp_input = self.temp_dir / f"{os.urandom(8).hex()}_protected.json"
        temp_recipient_priv = self.temp_dir / f"{os.urandom(8).hex()}_recipient_priv.key"
        temp_output = self.temp_dir / f"{os.urandom(8).hex()}_decrypted.json"
        
        try:
            temp_input.write_bytes(protected_document)
            temp_recipient_priv.write_bytes(recipient_priv_key)
            
            args = [
                str(temp_input),
                str(temp_recipient_priv),
                str(temp_output)
            ]
            
            success, stdout, stderr = self._run_java_command("unprotect", args)
            
            if success and temp_output.exists():
                decrypted_doc = temp_output.read_bytes()
                return True, decrypted_doc, stdout
            else:
                return False, None, stderr or stdout
        
        finally:
            for f in [temp_input, temp_recipient_priv, temp_output]:
                try:
                    if f.exists():
                        f.unlink()
                except:
                    pass
    
    def share(
        self,
        protected_document: bytes,
        new_recipient_pub_key: bytes,
        new_recipient_name: str,
        sharer_priv_key: bytes,
        sharer_name: str
    ) -> Tuple[bool, Optional[bytes], str]:
        """
        Share a protected document with a new recipient.
        
        Returns:
            Tuple of (success, shared_document_bytes, error_message)
        """
        temp_input = self.temp_dir / f"{os.urandom(8).hex()}_protected.json"
        temp_new_recipient_pub = self.temp_dir / f"{os.urandom(8).hex()}_new_recipient_pub.key"
        temp_sharer_priv = self.temp_dir / f"{os.urandom(8).hex()}_sharer_priv.key"
        temp_output = self.temp_dir / f"{os.urandom(8).hex()}_shared.json"
        
        try:
            temp_input.write_bytes(protected_document)
            temp_new_recipient_pub.write_bytes(new_recipient_pub_key)
            temp_sharer_priv.write_bytes(sharer_priv_key)
            
            args = [
                str(temp_input),
                str(temp_new_recipient_pub),
                new_recipient_name,
                str(temp_sharer_priv),
                sharer_name,
                str(temp_output)
            ]
            
            success, stdout, stderr = self._run_java_command("share", args)
            
            if success and temp_output.exists():
                shared_doc = temp_output.read_bytes()
                return True, shared_doc, stdout
            else:
                return False, None, stderr or stdout
        
        finally:
            for f in [temp_input, temp_new_recipient_pub, temp_sharer_priv, temp_output]:
                try:
                    if f.exists():
                        f.unlink()
                except:
                    pass

