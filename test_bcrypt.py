import bcrypt
h = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode()
print('Hash:', h)
print('Verify:', bcrypt.checkpw(b'admin123', h.encode()))
