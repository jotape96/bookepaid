import hashlib
password = "manager123"
print(hashlib.sha256(password.encode()).hexdigest())