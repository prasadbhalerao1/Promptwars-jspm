-- Seed database with sample users for all 5 roles
-- Run with: psql -d talent_platform -f seed_db.sql

-- Contributor role users
INSERT INTO users (id, email, password_hash, full_name, username, role, is_active, created_at, updated_at)
VALUES (
  '550e8400-e29b-41d4-a716-446655440001'::uuid,
  'alice@example.com',
  '$2b$12$slYQmyNdGzin7olVyON1Je4Zlv8Z2xM8nGKmHXQM1Xs5d7i5vLDDW', -- password123
  'Alice Chen',
  'alice_dev',
  'contributor',
  true,
  NOW(),
  NOW()
) ON CONFLICT (email) DO NOTHING;

INSERT INTO users (id, email, password_hash, full_name, username, role, is_active, created_at, updated_at)
VALUES (
  '550e8400-e29b-41d4-a716-446655440002'::uuid,
  'bob@example.com',
  '$2b$12$slYQmyNdGzin7olVyON1Je4Zlv8Z2xM8nGKmHXQM1Xs5d7i5vLDDW', -- password123
  'Bob Wilson',
  'bob_coder',
  'contributor',
  true,
  NOW(),
  NOW()
) ON CONFLICT (email) DO NOTHING;

INSERT INTO users (id, email, password_hash, full_name, username, role, is_active, created_at, updated_at)
VALUES (
  '550e8400-e29b-41d4-a716-446655440003'::uuid,
  'charlie@example.com',
  '$2b$12$slYQmyNdGzin7olVyON1Je4Zlv8Z2xM8nGKmHXQM1Xs5d7i5vLDDW', -- password123
  'Charlie Davis',
  'charlie_dev',
  'contributor',
  true,
  NOW(),
  NOW()
) ON CONFLICT (email) DO NOTHING;

-- Recruiter role users
INSERT INTO users (id, email, password_hash, full_name, username, role, is_active, created_at, updated_at)
VALUES (
  '550e8400-e29b-41d4-a716-446655440101'::uuid,
  'recruiter1@company.com',
  '$2b$12$slYQmyNdGzin7olVyON1Je4Zlv8Z2xM8nGKmHXQM1Xs5d7i5vLDDW', -- password123
  'Sarah Johnson',
  'sarah_recruiter',
  'recruiter',
  true,
  NOW(),
  NOW()
) ON CONFLICT (email) DO NOTHING;

INSERT INTO users (id, email, password_hash, full_name, username, role, is_active, created_at, updated_at)
VALUES (
  '550e8400-e29b-41d4-a716-446655440102'::uuid,
  'recruiter2@company.com',
  '$2b$12$slYQmyNdGzin7olVyON1Je4Zlv8Z2xM8nGKmHXQM1Xs5d7i5vLDDW', -- password123
  'Mike Chen',
  'mike_recruiter',
  'recruiter',
  true,
  NOW(),
  NOW()
) ON CONFLICT (email) DO NOTHING;

-- Organizer role users
INSERT INTO users (id, email, password_hash, full_name, username, role, is_active, created_at, updated_at)
VALUES (
  '550e8400-e29b-41d4-a716-446655440201'::uuid,
  'organizer@hackathon.io',
  '$2b$12$slYQmyNdGzin7olVyON1Je4Zlv8Z2xM8nGKmHXQM1Xs5d7i5vLDDW', -- password123
  'Emma Wilson',
  'emma_organizer',
  'organizer',
  true,
  NOW(),
  NOW()
) ON CONFLICT (email) DO NOTHING;

-- Judge role users
INSERT INTO users (id, email, password_hash, full_name, username, role, is_active, created_at, updated_at)
VALUES (
  '550e8400-e29b-41d4-a716-446655440301'::uuid,
  'judge1@hackathon.io',
  '$2b$12$slYQmyNdGzin7olVyON1Je4Zlv8Z2xM8nGKmHXQM1Xs5d7i5vLDDW', -- password123
  'Dr. Robert Smith',
  'robert_judge',
  'judge',
  true,
  NOW(),
  NOW()
) ON CONFLICT (email) DO NOTHING;

INSERT INTO users (id, email, password_hash, full_name, username, role, is_active, created_at, updated_at)
VALUES (
  '550e8400-e29b-41d4-a716-446655440302'::uuid,
  'judge2@hackathon.io',
  '$2b$12$slYQmyNdGzin7olVyON1Je4Zlv8Z2xM8nGKmHXQM1Xs5d7i5vLDDW', -- password123
  'Prof. Lisa Anderson',
  'lisa_judge',
  'judge',
  true,
  NOW(),
  NOW()
) ON CONFLICT (email) DO NOTHING;

-- Admin role users
INSERT INTO users (id, email, password_hash, full_name, username, role, is_active, created_at, updated_at)
VALUES (
  '550e8400-e29b-41d4-a716-446655440401'::uuid,
  'admin@trace.dev',
  '$2b$12$slYQmyNdGzin7olVyON1Je4Zlv8Z2xM8nGKmHXQM1Xs5d7i5vLDDW', -- password123
  'Admin User',
  'admin',
  'admin',
  true,
  NOW(),
  NOW()
) ON CONFLICT (email) DO NOTHING;

-- Print results
SELECT 'Seeded ' || count(*) || ' users' as result FROM users;
