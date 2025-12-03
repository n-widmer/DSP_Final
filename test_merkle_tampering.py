"""
Test script: Insert test patients, compute Merkle root, verify queries,
then simulate tampering and show integrity detection.

Usage:
    python test_merkle_tampering.py

Requirements:
    - MySQL connection configured in .env (MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB)
    - Patients table exists with row_hash column
    - merkle.py and userAuth.py in same directory
"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import Flask app and helpers
from app import mysql, app
from userAuth import (
    compute_patient_row_hash,
    insert_patient_with_hash,
    compute_patients_merkle_root,
    get_patient_with_merkle_proof,
)
from merkle import hex_to_bytes, verify_proof


def setup_test_patients():
    """Insert 3 test patients with auto-computed row hashes."""
    print("\n" + "="*60)
    print("STEP 1: Inserting test patients with row hashes")
    print("="*60)
    
    test_patients = [
        {
            "first_name": "Alice",
            "last_name": "Smith",
            "health_history": "No allergies",
            "gender": "F",
            "age": 28,
            "weight": 65.5,
            "height": 170.0,
        },
        {
            "first_name": "Bob",
            "last_name": "Johnson",
            "health_history": "Hypertension",
            "gender": "M",
            "age": 45,
            "weight": 85.0,
            "height": 180.0,
        },
        {
            "first_name": "Carol",
            "last_name": "Williams",
            "health_history": "Diabetes Type 2",
            "gender": "F",
            "age": 52,
            "weight": 72.3,
            "height": 165.0,
        },
    ]
    
    with app.app_context():
        cursor = mysql.connection.cursor()
        for patient in test_patients:
            success = insert_patient_with_hash(
                cursor,
                patient["first_name"],
                patient["last_name"],
                patient["health_history"],
                patient["gender"],
                patient["age"],
                patient["weight"],
                patient["height"],
            )
            if success:
                print(f"✓ Inserted: {patient['first_name']} {patient['last_name']}")
            else:
                print(f"✗ Failed to insert: {patient['first_name']} {patient['last_name']}")
        
        mysql.connection.commit()
        cursor.close()
    
    print("\nPatients inserted successfully!")


def compute_root():
    """Compute and store the Merkle root."""
    print("\n" + "="*60)
    print("STEP 2: Computing Merkle root from all patients")
    print("="*60)
    
    with app.app_context():
        root = compute_patients_merkle_root()
        if root:
            print(f"✓ Merkle root computed and stored locally:")
            print(f"  Root: {root[:32]}... (truncated)")
            return root
        else:
            print("✗ Failed to compute Merkle root")
            return None


def verify_patient_query(patient_id: int, root: str):
    """Query a patient with proof and verify integrity."""
    print(f"\n" + "="*60)
    print(f"STEP 3a: Querying patient {patient_id} (integrity intact)")
    print("="*60)
    
    with app.app_context():
        result = get_patient_with_merkle_proof(patient_id)
        if not result:
            print(f"✗ Patient {patient_id} not found")
            return False
        
        patient = result.get("patient")
        row_hash_hex = result.get("row_hash")
        proof_data = result.get("proof")
        merkle_root = result.get("merkle_root")
        
        print(f"✓ Retrieved patient: {patient['first_name']} {patient['last_name']}")
        print(f"  Row hash: {row_hash_hex[:32]}... (truncated)")
        print(f"  Merkle root: {merkle_root[:32]}... (truncated)")
        print(f"  Proof length: {len(proof_data)} sibling hashes")
        
        # Verify proof manually
        from merkle import verify_proof
        try:
            row_hash_bytes = hex_to_bytes(row_hash_hex)
            merkle_root_bytes = hex_to_bytes(merkle_root)
            proof_tuples = [(hex_to_bytes(sibling), is_left) for sibling, is_left in proof_data]
            
            is_valid = verify_proof(row_hash_bytes, proof_tuples, merkle_root_bytes)
            if is_valid:
                print(f"✓ Merkle proof VERIFIED successfully")
                return True
            else:
                print(f"✗ Merkle proof FAILED verification")
                return False
        except Exception as e:
            print(f"✗ Error during verification: {e}")
            return False


def simulate_tampering(patient_id: int):
    """Directly modify patient data in database (bypass row_hash update)."""
    print("\n" + "="*60)
    print(f"STEP 4: SIMULATING TAMPERING - modifying patient {patient_id} data in DB")
    print("="*60)
    
    with app.app_context():
        cursor = mysql.connection.cursor()
        try:
            # Modify patient's health_history WITHOUT updating row_hash
            # This breaks the integrity guarantee
            cursor.execute(
                "UPDATE Patients SET health_history = %s WHERE id = %s",
                ("TAMPERED: Unauthorized modification detected!", patient_id)
            )
            mysql.connection.commit()
            print(f"✓ Patient {patient_id} data modified (row_hash NOT updated)")
            print(f"  Change: health_history updated to 'TAMPERED: Unauthorized modification detected!'")
            print(f"  Note: row_hash was NOT recomputed (simulating unauthorized DB access)")
        except Exception as e:
            print(f"✗ Error during tampering: {e}")
        finally:
            cursor.close()


def verify_patient_after_tampering(patient_id: int):
    """Query the tampered patient and show integrity detection."""
    print("\n" + "="*60)
    print(f"STEP 5: Querying tampered patient {patient_id} (should FAIL verification)")
    print("="*60)
    
    with app.app_context():
        result = get_patient_with_merkle_proof(patient_id)
        if not result:
            print(f"✗ Patient {patient_id} not found")
            return False
        
        patient = result.get("patient")
        row_hash_hex = result.get("row_hash")
        proof_data = result.get("proof")
        merkle_root = result.get("merkle_root")
        
        print(f"✓ Retrieved patient: {patient['first_name']} {patient['last_name']}")
        print(f"  Row hash (old, stored in DB): {row_hash_hex[:32]}... (truncated)")
        print(f"  Current health_history: {patient['health_history']}")
        print(f"  Merkle root (trusted): {merkle_root[:32]}... (truncated)")

        # Compute expected hash from received patient data
        expected_hash_hex = compute_patient_row_hash(patient)
        print(f"  Expected hash from data: {expected_hash_hex[:32]}... (truncated)")

        if expected_hash_hex != row_hash_hex:
            print(f"\n🚨 ALERT: Data integrity breach detected!")
            print(f"   Expected hash: {expected_hash_hex}")
            print(f"   Stored hash:   {row_hash_hex}")
            print(f"   The data does not match the stored row_hash. Tampering suspected!")
            return False

        # Verify proof manually
        from merkle import verify_proof
        try:
            row_hash_bytes = hex_to_bytes(row_hash_hex)
            merkle_root_bytes = hex_to_bytes(merkle_root)
            proof_tuples = [(hex_to_bytes(sibling), is_left) for sibling, is_left in proof_data]
            
            is_valid = verify_proof(row_hash_bytes, proof_tuples, merkle_root_bytes)
            if is_valid:
                print(f"✓ Merkle proof verified (unexpected!)")
                return True
            else:
                print(f"\n🚨 ALERT: Merkle proof FAILED verification")
                print(f"   ===== DATA INTEGRITY BREACH DETECTED =====")
                print(f"   Patient {patient_id}'s data does not match the stored row_hash.")
                print(f"   Possible tampering or corruption detected!")
                print(f"   Action: Reject this query, alert administrator")
                return False
        except Exception as e:
            print(f"✗ Error during verification: {e}")
            return False


def recompute_root_after_tampering():
    """Show what happens when we recompute root after tampering."""
    print("\n" + "="*60)
    print("STEP 6: Recomputing Merkle root after tampering (with old row_hash)")
    print("="*60)
    
    with app.app_context():
        root = compute_patients_merkle_root()
        if root:
            print(f"✓ New Merkle root computed:")
            print(f"  Root: {root[:32]}... (truncated)")
            print(f"\nNote: The root changed because patient 2's row_hash is still the old one.")
            print(f"      To fix integrity, must recompute row_hash for tampered patient.")
        else:
            print("✗ Failed to compute Merkle root")


def cleanup_test_data():
    """Delete test patients."""
    print("\n" + "="*60)
    print("CLEANUP: Deleting test patients")
    print("="*60)
    
    with app.app_context():
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("DELETE FROM Patients WHERE first_name IN (%s, %s, %s)", 
                          ("Alice", "Bob", "Carol"))
            mysql.connection.commit()
            print(f"✓ Test patients deleted")
        except Exception as e:
            print(f"✗ Error during cleanup: {e}")
        finally:
            cursor.close()


def main():
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "MERKLE TREE TAMPERING TEST" + " "*17 + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        # Step 1: Insert test patients
        setup_test_patients()
        
        # Step 2: Compute Merkle root
        root = compute_root()
        if not root:
            print("Failed to compute root. Exiting.")
            return
        
        # Step 3: Verify a patient (should pass)
        patient_1_valid = verify_patient_query(1, root)
        
        # Step 4: Simulate tampering
        simulate_tampering(2)
        
        # Step 5: Verify tampered patient (should fail)
        patient_2_tampered = verify_patient_after_tampering(2)
        
        # Step 6: Show what happens with recomputation
        recompute_root_after_tampering()
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Patient 1 (unmodified) verification: {'✓ PASSED' if patient_1_valid else '✗ FAILED'}")
        print(f"Patient 2 (tampered) verification: {'✓ PASSED (unexpected)' if patient_2_tampered else '✗ FAILED (expected)'}")
        print(f"\nConclusion: Merkle tree {'successfully' if (patient_1_valid and not patient_2_tampered) else 'FAILED to'} detect tampering!")
        
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        cleanup_test_data()
        print("\n✓ Test complete!")


if __name__ == "__main__":
    main()
