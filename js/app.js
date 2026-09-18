// 여러 페이지에서 함께 쓰는 공통 함수들

function won(n) {
  return Math.round(Number(n)).toLocaleString('ko-KR') + '원';
}

function pct(n) {
  const v = Number(n);
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
}

function signClass(n) {
  if (Number(n) > 0) return 'up';
  if (Number(n) < 0) return 'down';
  return '';
}

async function currentUser() {
  const { data } = await db.auth.getUser();
  return data.user;
}

async function requireLogin() {
  const user = await currentUser();
  if (!user) {
    location.href = 'index.html';
    return null;
  }
  return user;
}

async function logout() {
  await db.auth.signOut();
  location.href = 'index.html';
}

async function myProfile() {
  const user = await currentUser();
  if (!user) return null;
  const { data, error } = await db
    .from('profiles')
    .select('nickname, cash')
    .eq('id', user.id)
    .single();
  if (error) {
    console.error(error);
    return null;
  }
  return data;
}