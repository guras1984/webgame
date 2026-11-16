import { createServer } from 'node:http';
import { randomBytes, randomInt } from 'node:crypto';
import { readFile } from 'node:fs/promises';

const page = await readFile(new URL('./index.html', import.meta.url));
const rooms = new Map();
const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
const colors = ['#ffb46b', '#69e4b7', '#b99aff', '#71caff'];
const spawns = [[2, 2], [9, 2], [2, 9], [9, 9]];
const gems = [[1, 5], [4, 2], [8, 3], [10, 6], [8, 9], [4, 10], [6, 6]];
const walls = [[3,4],[3,5],[3,6],[7,4],[8,4],[7,8],[4,7]];
const allowed = new Set((process.env.ALLOWED_ORIGINS ?? 'https://guras1984.github.io').split(','));
const ttl = 25000;

function snapshot(room, token) {
  return {
    code: room.code, self: room.players.get(token).id,
    players: [...room.players.values()].map(({id, name, color, x, y, score}) =>
      ({id, name, color, x, y, score})),
    gems: room.gems.map((ready, i) => ready <= Date.now() ? i : -1).filter(i => i >= 0)
  };
}

function sweep(now) {
  for (const [code, room] of rooms) {
    for (const [token, player] of room.players) {
      if (now - player.last > ttl) room.players.delete(token);
    }
    if (!room.players.size) rooms.delete(code);
  }
}

function game(input) {
  const now = Date.now();
  sweep(now);
  if (input.action === 'create' || input.action === 'join') {
    const name = typeof input.name === 'string' ? input.name.trim().slice(0, 12) : '';
    if (!name) return [400, {error:'닉네임을 입력해 주세요.'}];
    let room = rooms.get(input.code);
    if (input.action === 'create') {
      if (rooms.size >= 64) return [503, {error:'현재 방이 많아요. 잠시 후 다시 시도해 주세요.'}];
      let code;
      do {
        code = Array.from({length:6}, () => alphabet[randomInt(alphabet.length)]).join('');
      } while (rooms.has(code));
      room = {code, players:new Map(), gems:gems.map(() => 0)};
      rooms.set(code, room);
    }
    if (!room) return [404, {error:'방을 찾을 수 없어요. 코드를 확인해 주세요.'}];
    if (room.players.size >= 4) return [409, {error:'방이 가득 찼어요.'}];
    const slot = colors.findIndex(color => ![...room.players.values()].some(p => p.color === color));
    const [x, y] = spawns[slot];
    const token = randomBytes(24).toString('hex');
    room.players.set(token, {id:randomBytes(8).toString('hex'), name, x, y, score:0, color:colors[slot], last:now});
    return [200, {...snapshot(room, token), token}];
  }

  const room = rooms.get(input.code);
  const player = room?.players.get(input.token);
  if (!player) return [410, {error:'연결이 만료됐어요. 방에 다시 입장해 주세요.'}];
  if (input.action === 'leave') {
    room.players.delete(input.token);
    if (!room.players.size) rooms.delete(room.code);
    return [200, {}];
  }
  if (input.action !== 'step') return [400, {error:'잘못된 요청이에요.'}];

  let dx = [-1, 0, 1].includes(input.dx) ? input.dx : 0;
  let dy = [-1, 0, 1].includes(input.dy) ? input.dy : 0;
  const length = Math.hypot(dx, dy) || 1;
  const distance = Math.min((now - player.last) / 1000, .18) * 3.5;
  player.last = now;
  const inside = (x, y) => x >= .35 && x <= 11.65 && y >= .35 && y <= 11.65 &&
    !walls.some(([wx, wy]) => Math.abs(x - wx) < .66 && Math.abs(y - wy) < .66);
  dx = dx / length * distance;
  dy = dy / length * distance;
  if (inside(player.x + dx, player.y)) player.x += dx;
  if (inside(player.x, player.y + dy)) player.y += dy;
  for (const [i, [x, y]] of gems.entries()) {
    if (room.gems[i] <= now && Math.hypot(player.x - x, player.y - y) < .55) {
      room.gems[i] = now + 12000;
      player.score++;
    }
  }
  return [200, snapshot(room, input.token)];
}

createServer(async (req, res) => {
  const origin = req.headers.origin;
  const sameOrigin = origin === `http://${req.headers.host}` || origin === `https://${req.headers.host}`;
  if (origin && (allowed.has(origin) || sameOrigin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Vary', 'Origin');
  }
  const send = (status, body) => {
    res.writeHead(status, {'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});
    res.end(JSON.stringify(body));
  };
  if (req.method === 'GET' && req.url === '/health') return send(200, {ok:true});
  if (req.method === 'GET' && req.url.split('?', 1)[0] === '/') {
    res.writeHead(200, {'Content-Type':'text/html; charset=utf-8'});
    return res.end(page);
  }
  if (req.method !== 'POST' || req.url !== '/play') return send(404, {});
  if (origin && !allowed.has(origin) && !sameOrigin) return send(403, {});
  try {
    let body = '';
    for await (const chunk of req) {
      body += chunk;
      if (body.length > 2048) return send(413, {});
    }
    const input = JSON.parse(body);
    if (!input || typeof input !== 'object') return send(400, {});
    const [status, result] = game(input);
    send(status, result);
  } catch {
    send(400, {error:'요청을 처리하지 못했어요.'});
  }
}).listen(Number(process.env.PORT ?? 8787), process.env.HOST ?? '0.0.0.0');
