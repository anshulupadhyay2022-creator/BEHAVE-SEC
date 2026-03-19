#!/usr/bin/env python3
"""
Test Script for BEHAVE-SEC Backend API
Tests all endpoints and data collection functionality
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8000"

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def test_root_endpoint():
    """Test the root endpoint"""
    print_header("TEST 1: Root Endpoint")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Root endpoint test PASSED")
            return True
        else:
            print("❌ Root endpoint test FAILED")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        print("⚠️  Make sure the backend server is running!")
        return False

def test_collect_data_endpoint():
    """Test the /collect-data endpoint with sample data"""
    print_header("TEST 2: Collect Data Endpoint")
    
    # Sample behavioral data payload
    sample_payload = {
        "userId": "test_user_001",
        "sessionId": str(int(time.time() * 1000)),
        "events": [
            {
                "eventType": "keydown",
                "timestamp": int(time.time() * 1000),
                "relativeTime": 1000,
                "key": "a",
                "keyCode": 65,
                "target": "INPUT",
                "targetId": "test-input",
                "targetName": "test"
            },
            {
                "eventType": "keyup",
                "timestamp": int(time.time() * 1000) + 100,
                "relativeTime": 1100,
                "key": "a",
                "keyCode": 65,
                "target": "INPUT",
                "targetId": "test-input",
                "targetName": "test"
            },
            {
                "eventType": "mousemove",
                "timestamp": int(time.time() * 1000) + 200,
                "relativeTime": 1200,
                "clientX": 450,
                "clientY": 300,
                "pageX": 450,
                "pageY": 800,
                "target": "DIV",
                "targetId": None
            }
        ],
        "metadata": {
            "userAgent": "Test Script/1.0",
            "screenWidth": 1920,
            "screenHeight": 1080,
            "sessionDuration": 5000
        }
    }
    
    try:
        print("\nSending sample payload...")
        print(f"Events: {len(sample_payload['events'])}")
        
        response = requests.post(
            f"{BASE_URL}/collect-data",
            json=sample_payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("\n✅ Collect data endpoint test PASSED")
            return True
        else:
            print("\n❌ Collect data endpoint test FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_stats_endpoint():
    """Test the /stats endpoint"""
    print_header("TEST 3: Statistics Endpoint")
    
    try:
        response = requests.get(f"{BASE_URL}/stats")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nStatistics:")
            print(f"  Total Sessions: {data['totalSessions']}")
            print(f"  Total Events: {data['totalEvents']}")
            
            if data['sessions']:
                print(f"\n  Recent Sessions:")
                for session in data['sessions'][:3]:  # Show first 3
                    print(f"    - Session {session['sessionId']}: {session['eventCount']} events")
            
            print("\n✅ Statistics endpoint test PASSED")
            return True
        else:
            print("❌ Statistics endpoint test FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_invalid_data():
    """Test validation with invalid data"""
    print_header("TEST 4: Data Validation")
    
    # Invalid payload - missing required fields
    invalid_payload = {
        "userId": "test_user",
        "events": []  # Empty events list should fail
    }
    
    try:
        print("\nSending invalid payload (should fail validation)...")
        
        response = requests.post(
            f"{BASE_URL}/collect-data",
            json=invalid_payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 422:  # Validation error expected
            print("\n✅ Data validation test PASSED (correctly rejected invalid data)")
            return True
        else:
            print("\n⚠️  Expected validation error (422), got different response")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("\n" + "🧪" * 30)
    print("  BEHAVE-SEC Backend API Test Suite")
    print("🧪" * 30)
    
    results = []
    
    # Test 1: Root endpoint
    results.append(("Root Endpoint", test_root_endpoint()))
    
    # Only continue if server is reachable
    if not results[0][1]:
        print_header("TESTS ABORTED")
        print("⚠️  Backend server is not running or not reachable")
        print("   Please start the server first: python backend_api.py")
        return
    
    # Test 2: Collect data
    results.append(("Collect Data", test_collect_data_endpoint()))
    
    # Test 3: Statistics
    results.append(("Statistics", test_stats_endpoint()))
    
    # Test 4: Validation
    results.append(("Data Validation", test_invalid_data()))
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Backend is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    run_all_tests()
