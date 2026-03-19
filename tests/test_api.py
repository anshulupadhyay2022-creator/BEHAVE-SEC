#!/usr/bin/env python3
"""
Test Script for BEHAVE-SEC Backend API
Tests all endpoints and data collection functionality.

Usage:
    # Make sure the server is running first:
    #   python init_backend.py
    python tests/test_api.py
"""

import json
import time

import requests

BASE_URL = "http://localhost:8000"


def print_header(text: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def test_root_endpoint() -> bool:
    print_header("TEST 1: Root Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        if response.status_code == 200:
            print("✅ Root endpoint test PASSED")
            return True
        print("❌ Root endpoint test FAILED")
        return False
    except Exception as exc:
        print(f"❌ Error: {exc}")
        print("⚠️  Make sure the backend server is running:  python init_backend.py")
        return False


def test_collect_data_endpoint() -> bool:
    print_header("TEST 2: Collect Data Endpoint")
    sample_payload = {
        "userId":    "test_user_001",
        "sessionId": str(int(time.time() * 1000)),
        "events": [
            {
                "eventType":   "keydown",
                "timestamp":   int(time.time() * 1000),
                "relativeTime": 1000,
                "key":         "a",
                "keyCode":     65,
                "target":      "INPUT",
                "targetId":    "test-input",
                "targetName":  "test",
            },
            {
                "eventType":   "keyup",
                "timestamp":   int(time.time() * 1000) + 100,
                "relativeTime": 1100,
                "key":         "a",
                "keyCode":     65,
                "target":      "INPUT",
                "targetId":    "test-input",
                "targetName":  "test",
            },
            {
                "eventType":    "mousemove",
                "timestamp":    int(time.time() * 1000) + 200,
                "relativeTime": 1200,
                "clientX":      450,
                "clientY":      300,
                "pageX":        450,
                "pageY":        800,
                "target":       "DIV",
                "targetId":     None,
            },
        ],
        "metadata": {
            "userAgent":       "Test Script/1.0",
            "screenWidth":     1920,
            "screenHeight":    1080,
            "sessionDuration": 5000,
        },
    }
    try:
        print(f"\nSending {len(sample_payload['events'])} events ...")
        response = requests.post(
            f"{BASE_URL}/collect-data",
            json=sample_payload,
            headers={"Content-Type": "application/json"},
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        if response.status_code == 200:
            print("\n✅ Collect data endpoint test PASSED")
            return True
        print("\n❌ Collect data endpoint test FAILED")
        return False
    except Exception as exc:
        print(f"❌ Error: {exc}")
        return False


def test_stats_endpoint() -> bool:
    print_header("TEST 3: Statistics Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/stats")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"\n  Total Sessions : {data['totalSessions']}")
            print(f"  Total Events   : {data['totalEvents']}")
            if data["sessions"]:
                print("\n  Recent Sessions:")
                for s in data["sessions"][:3]:
                    print(f"    - {s['sessionId']}: {s['eventCount']} events")
            print("\n✅ Statistics endpoint test PASSED")
            return True
        print("❌ Statistics endpoint test FAILED")
        return False
    except Exception as exc:
        print(f"❌ Error: {exc}")
        return False


def test_invalid_data() -> bool:
    print_header("TEST 4: Data Validation")
    invalid_payload = {"userId": "test_user", "events": []}
    try:
        print("\nSending invalid payload (should be rejected) ...")
        response = requests.post(
            f"{BASE_URL}/collect-data",
            json=invalid_payload,
            headers={"Content-Type": "application/json"},
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 422:
            print("\n✅ Data validation test PASSED (correctly rejected invalid data)")
            return True
        print(f"\n⚠️  Expected 422, got {response.status_code}")
        return False
    except Exception as exc:
        print(f"❌ Error: {exc}")
        return False


def run_all_tests() -> None:
    print("\n" + "🧪" * 30)
    print("  BEHAVE-SEC Backend API Test Suite")
    print("🧪" * 30)

    results = []

    results.append(("Root Endpoint", test_root_endpoint()))
    if not results[0][1]:
        print_header("TESTS ABORTED")
        print("⚠️  Server not reachable — run:  python init_backend.py")
        return

    results.append(("Collect Data",   test_collect_data_endpoint()))
    results.append(("Statistics",     test_stats_endpoint()))
    results.append(("Data Validation", test_invalid_data()))

    print_header("TEST SUMMARY")
    passed = sum(1 for _, r in results if r)
    for name, result in results:
        print(f"  {'✅ PASS' if result else '❌ FAIL'}  {name}")
    print(f"\n  Total: {passed}/{len(results)} tests passed")
    if passed == len(results):
        print("\n  🎉 All tests passed! Backend is working correctly.")
    else:
        print("\n  ⚠️  Some tests failed — check output above.")


if __name__ == "__main__":
    run_all_tests()
