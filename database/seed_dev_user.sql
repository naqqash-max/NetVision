-- Seed Initial Administrator for Development (password: admin123, hashed with bcrypt)
INSERT INTO users (id, email, username, hashed_password, full_name, role, is_active)
VALUES (
    'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
    'admin@netvision.com',
    'admin',
    '$2b$12$A04joZlkeRv1o2NlE06o2.TRGL.koKQ8g9S1ZgxrKNPA6koJrNBCy', -- admin123 bcrypt hash
    'System Administrator',
    'ADMIN',
    TRUE
) ON CONFLICT DO NOTHING;
