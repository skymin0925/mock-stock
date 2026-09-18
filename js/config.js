// Supabase 연결 설정
const SUPABASE_URL = 'https://crqcafbvmxdmhwypmewy.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNycWNhZmJ2bXhkbWh3eXBtZXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODk2MzI3NTAsImV4cCI6MjEwNTIwODc1MH0.dYJE_DSnq3GqPcdE3bTkhvomDSC3dEjG7fGzsyXTcmA';

// anon key 는 공개되어도 안전합니다 (RLS 가 데이터를 보호합니다).
// service_role key 는 절대 여기에 넣지 마세요!
const db = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);