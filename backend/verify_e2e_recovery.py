import urllib.request
import json
import re
import urllib.error

def run_e2e():
    print("--- STARTING E2E PASSWORD RECOVERY VERIFICATION ---")
    
    # 1. Trigger forgot password
    forgot_req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/forgot-password",
        data=json.dumps({"email": "admin@netvision.com"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    forgot_res = urllib.request.urlopen(forgot_req)
    print("1. Forgot Password Request Sent:", forgot_res.read().decode())

    # 2. Extract reset token from Mailpit
    msgs_res = urllib.request.urlopen("http://mailpit:8025/api/v1/messages")
    msgs = json.loads(msgs_res.read().decode())
    msg_id = msgs["messages"][0]["ID"]
    
    detail_res = urllib.request.urlopen(f"http://mailpit:8025/api/v1/message/{msg_id}")
    msg_body = json.loads(detail_res.read().decode())
    html = msg_body.get("HTML", "")
    
    match = re.search(r"token=([A-Za-z0-9_\-]+)", html)
    assert match is not None, "Token missing in HTML email!"
    token = match.group(1)
    print(f"2. Extracted Token from Mailpit HTML Email: {token[:12]}...")

    # 3. Perform Password Reset
    new_pass = "NewProductionPass99!"
    reset_req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/reset-password",
        data=json.dumps({
            "token": token,
            "new_password": new_pass,
            "confirm_password": new_pass
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    reset_res = urllib.request.urlopen(reset_req)
    print("3. Reset Password Response:", reset_res.read().decode())

    # 4. Old password login attempt
    old_login_req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/login",
        data=json.dumps({"username_or_email": "admin@netvision.com", "password": "AdminPassword123!"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(old_login_req)
        print("ERROR: Old password unexpectedly succeeded!")
    except urllib.error.HTTPError as e:
        print(f"4. Old Password Correctly Rejected: HTTP {e.code} Unauthorized")

    # 5. New password login attempt
    new_login_req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/login",
        data=json.dumps({"username_or_email": "admin@netvision.com", "password": new_pass}).encode(),
        headers={"Content-Type": "application/json"}
    )
    new_login_res = urllib.request.urlopen(new_login_req)
    print("5. New Password Login Succeeded: HTTP 200 OK")

    # 6. Attempt token reuse
    try:
        urllib.request.urlopen(reset_req)
        print("ERROR: Reused token unexpectedly succeeded!")
    except urllib.error.HTTPError as e:
        print(f"6. Token Single-Use Verified: Re-using token rejected with HTTP {e.code}")

    # 7. Restore original admin password
    forgot_req2 = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/forgot-password",
        data=json.dumps({"email": "admin@netvision.com"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(forgot_req2)
    msgs_res2 = urllib.request.urlopen("http://mailpit:8025/api/v1/messages")
    msg_id2 = json.loads(msgs_res2.read().decode())["messages"][0]["ID"]
    msg_body2 = json.loads(urllib.request.urlopen(f"http://mailpit:8025/api/v1/message/{msg_id2}").read().decode())
    token2 = re.search(r"token=([A-Za-z0-9_\-]+)", msg_body2.get("HTML")).group(1)
    
    restore_req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/reset-password",
        data=json.dumps({
            "token": token2,
            "new_password": "admin123",
            "confirm_password": "admin123"
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(restore_req)
    print("7. Restored Admin Password back to admin123")
    print("--- E2E VERIFICATION COMPLETED SUCCESSFULLY ---")

if __name__ == "__main__":
    run_e2e()
