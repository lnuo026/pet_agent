# 🐾 生产级宠物急难分诊助手 — 完整实施计划

> **项目名称**：pet-triage  
> **目标**：将本地 n8n 通用聊天 bot 改造为生产级宠物急救分诊向导，真正部署上线  
> **计划日期**：2026-05-27  

---

## 一、项目背景与目标
我在做一个练手项目 pet-triage(宠物急难分诊助手),计划在 pet-triage-plan.md 里。我是编程有基础但 Python 和 LLM agent 是新手的学习者。请用「教我、不替我写」的方式带我:每一步解释在做什么、为什么这么做,默认我什么都不知道,讲清前置知识。

### 现状
- n8n v2.21.7 已运行在 Docker 容器（`localhost:5678`），是通用对话助手
- 已有完整生产部署经验：omniport 项目（EC2 + Docker + Nginx + GitHub Actions + Let's Encrypt）

[重要]不要自动修改我的任何文件。详细操作清单 + 每步原因，按生产级路线直接执行即可；ai不再反问，用户做完再提问题。

### 改造目标
| 维度 | 现在 | 改造后 |
|------|------|--------|
| 角色 | 通用 AI 助手 | 专业宠物急救分诊向导 |
| 紧急度判断 | 无 | 🔴🟡🟢 三级分诊 |
| 诊所推荐 | 无 | 根据城市查询低价/免费动物医院 |
| 访问方式 | localhost:5678（仅本地） | HTTPS 公网（7×24） |
| 对话记忆 | 无 | 多轮会话记忆 |
| 免责声明 | 无 | 首次弹窗强制确认 |
| 日志记录 | 无 | MongoDB Atlas 完整日志 |

---

## 二、系统架构

```
用户浏览器 (React + Vite + Tailwind)
    │
    │ HTTPS POST /api/chat/message
    ▼
Nginx (SSL终止, proxy_read_timeout 35s)
    │
    ├── /api/*  ──→  NestJS :3000
    │                   │ 限流(10次/min) + MongoDB日志
    │                   │ HTTP POST (内网, 35s超时)
    │                   ▼
    │               n8n :5678 (同一Docker network)
    │                   │
    │               ┌───┴──────────────────────────┐
    │               │  Chat Trigger (Session Memory) │
    │               │  → Code: 解析输入              │
    │               │  → Gemini 1.5 Flash           │
    │               │  → Code: 提取分诊标记          │
    │               │  → Google Sheets: 查询诊所    │
    │               │  → Code: 拼接最终回复          │
    │               │  Error Trigger: 回退话术       │
    │               └────────────────────────────── ┘
    │
    └── /*  ──────→  React 静态文件 (Nginx serve)
```

**部署策略**：EC2 同台服务器（复用 omniport 基础设施），新域名 `pettriage.yourdomain.com`。

---

## 三、项目目录结构

```
pet-triage/                           ← 新建 GitHub Repo
├── frontend/                         # React + Vite + Tailwind
│   ├── src/
│   │   ├── api/
│   │   │   ├── request.ts            # axios实例（复用omniport模式）
│   │   │   └── chat.api.ts           # POST /api/chat/message
│   │   ├── components/
│   │   │   ├── DisclaimerModal.tsx   # 首次强制弹窗，勾选才能继续
│   │   │   ├── ChatWindow.tsx        # 主聊天界面
│   │   │   ├── MessageBubble.tsx     # 消息气泡（用户/助手）
│   │   │   ├── TriageIndicator.tsx   # 🔴🟡🟢徽章（RED含脉冲动画）
│   │   │   └── TypingDots.tsx        # AI思考中动画
│   │   ├── store/chatStore.ts        # Zustand（sessionId持久化localStorage）
│   │   ├── types/chat.types.ts       # Message, TriageLevel, ChatRequest/Response
│   │   └── App.tsx
│   ├── Dockerfile                    # 复用omniport frontend.Dockerfile
│   └── nginx.conf                    # SPA路由(try_files)
│
├── backend/                          # NestJS API网关
│   ├── src/
│   │   ├── modules/chat/
│   │   │   ├── chat.module.ts
│   │   │   ├── chat.controller.ts    # POST /api/chat/message (@Public + Throttle)
│   │   │   ├── chat.service.ts       # 转发n8n + MongoDB日志
│   │   │   ├── chat.schema.ts        # ChatLog Schema
│   │   │   └── dto/send-message.dto.ts  # 验证 message(≤2000) + sessionId(UUID)
│   │   ├── common/                   # 完全复用omniport (filters/interceptors/decorators)
│   │   ├── health/                   # 复用omniport /api/health
│   │   ├── app.module.ts
│   │   └── main.ts
│   ├── Dockerfile                    # 复用omniport backend.Dockerfile
│   └── .env
│
├── infra/
│   ├── docker/docker-compose.yml     # 改自omniport（加n8n network）
│   └── nginx/nginx.conf              # 改自omniport（改域名+加35s超时）
│
└── .github/workflows/
    ├── ci.yml                        # 直接复用omniport CI
    └── cd.yml                        # 直接复用omniport CD（改secrets名）
```

---

## 四、n8n 工作流设计（7个节点）

### 节点流程图

```
[1. Chat Trigger]
      │
[2. Code: 解析sessionId]
      │
[3. AI Agent (Gemini)]  ← 系统提示词注入
      │
[4. Code: 提取分诊标记+城市]
      │
[5. Google Sheets: 查询诊所]
      │
[6. Code: 拼接最终回复]

[7. Error Trigger] ── 任意节点出错时触发 ──→ 回退话术
```

### 节点 1：Chat Trigger
- 开启 **Window Buffer Memory**（Context Window = 10，保留最近5轮对话）
- `sessionId` 由前端 localStorage 持久化并传入

### 节点 2：Code 节点（解析输入）
```javascript
const sessionId = $input.first().json.sessionId || 'anonymous';
const userMessage = $input.first().json.chatInput;
return [{ json: { sessionId, userMessage } }];
```

### 节点 3：AI Agent（Gemini 1.5 Flash）
- temperature: 0.3（稳定输出）
- System Message: **见第五章完整提示词**

### 节点 4：Code 节点（提取机器标记）
```javascript
const raw = $input.first().json.output;

// 解析三级紧急度（机器可读标记）
const triageLevel =
  raw.includes('[TRIAGE:RED]')    ? 'red'    :
  raw.includes('[TRIAGE:YELLOW]') ? 'yellow' : 'green';

// 解析城市
const cityMatch = raw.match(/\[CITY:([^\]]+)\]/);
const city = cityMatch ? cityMatch[1].trim() : null;

// 清除机器标记，保留用户可见内容
const cleanOutput = raw
  .replace(/\[TRIAGE:[A-Z]+\]/g, '')
  .replace(/\[CITY:[^\]]+\]/g, '')
  .trim();

return [{ json: { triageLevel, city, cleanOutput } }];
```
LLM 被要求每次回复时,在开头偷偷写一个标记,比如 [TRIAGE:RED]、[CITY:奥克兰]。
这些标记不给用户看,是写给程序看的。

为什么要这么做?
你想,LLM 输出的是一段自然语言「您的狗狗情况危急,请立即……」。可是程序怎么知道它判的是红还是绿?程序读不懂人话里的「危急」,但它能精准识别 [TRIAGE:RED] 这个固定标记。

所以这一步做的事是:让 LLM 在「说人话给用户」的同时,夹带一个「说机器话给程序」的信号,程序靠这个信号决定下一步要不要去查诊所、前端要不要亮红灯。

这个概念叫结构化输出,是 agent 工程里极其核心的一招——它解决了「AI 输出是自由发挥的文字,但程序需要确定的、能处理的数据」这个根本矛盾。

第四站:回到用户屏幕
最终用户看到的是:一段温和专业的话 + 一个红色脉冲的徽章(提示紧急)+ 附近诊所的名字电话。

同时这整段对话被默默记进了数据库,供你日后分析「AI 哪些场景答得不好」。



### 节点 5：Google Sheets 节点
- 操作：Read Rows | Sheet: `Clinics` | Range: `A:I`
- 条件：节点4中 `city` 不为空且 `triageLevel` 为 `red` 或 `yellow` 时才查询

### 节点 6：Code 节点（拼接诊所 + 最终输出）
```javascript
const { triageLevel, city, cleanOutput } = $node['节点4'].json;
const rows = $node['Sheets'].json.values || [];

const clinics = rows.map(r => ({
  city: r[0], name: r[2], phone: r[3], address: r[4], is24h: r[6] === 'TRUE'
}));

let clinicSection = '';
if (city && ['red', 'yellow'].includes(triageLevel)) {
  const matched = clinics
    .filter(c => c.city.includes(city) && c.is24h)
    .slice(0, 3);
  if (matched.length) {
    clinicSection = '\n\n**📍 附近24小时急诊动物医院：**\n' +
      matched.map(c => `• **${c.name}** | ${c.phone}\n  ${c.address}`).join('\n');
  }
}

return [{ json: {
  output: cleanOutput + clinicSection,
  triageLevel,
  sessionId: $node['节点2'].json.sessionId
}}];
```

### 节点 7：Error Trigger
```javascript
// 回退话术
return [{json: {
  output: '⚠️ 系统暂时遇到了问题，无法处理您的请求。\n\n如宠物处于紧急状态，**请立即拨打当地24小时动物医院急诊**，不要等待。\n\n我们将尽快恢复服务。',
  triageLevel: 'unknown'
}}];
```

---

## 五、完整系统提示词

> 粘贴到 n8n AI Agent 节点的 **System Message** 字段

```
你是「宠物急难分诊助手」，专注于宠物紧急情况评估，拒绝处理任何无关话题。

## 绝对规则（不可违反）
1. 每次回复第一行必须输出分诊标记（不向用户展示）：
   [TRIAGE:RED] 或 [TRIAGE:YELLOW] 或 [TRIAGE:GREEN]
2. 识别到城市名时输出：[CITY:城市名]（如 [CITY:奥克兰]）
3. 不诊断疾病，不推荐药物剂量，不替代兽医
4. 使用中文，语气温和专业

---

## 🔴 RED — 立即急诊（30分钟内，生命威胁）
触发任意一条即判 RED：
- 呼吸急促 / 张口呼吸 / 嘴唇发紫或发白
- 抽搐 / 无法站立 / 突然倒地 / 意识丧失
- 大量出血（超过1分钟无法止血）
- 怀疑误食毒物（农药、巧克力大量、洋葱、葡萄、人类药物等）
- 腹部极度膨胀（腹胀+干呕，疑似 GDV 胃扩张）
- 公猫超过12小时无尿（尿道堵塞危象）
- 眼球突出 / 第三眼睑暴露
- 难产超过2小时无进展
- 骨骼外露 / 严重骨折变形

RED 回复格式：
[TRIAGE:RED]
🔴 **需要立即急诊 — 生命威胁**

您的描述涉及严重紧急症状，**请立刻出发前往动物医院，不要等待观察**。

途中急救要点：
• [针对具体症状的1-2条简短急救建议]

[CITY:若用户提到城市则输出此标记]
*请告诉我您在哪个城市，我帮您查找最近的24小时急诊医院。*

---
⚠️ *本建议仅供参考，不构成医疗诊断。*

---

## 🟡 YELLOW — 今日就医（24小时内）
触发任意一条即判 YELLOW：
- 呕吐超过3次/24小时，或呕吐物带血
- 腹泻超过24小时，或含血
- 不进食超过48小时（猫超过24小时）
- 跛行（可负重但明显疼痛）
- 持续颤抖 / 哭叫 / 躲避抚摸
- 眼部大量分泌物 / 眼睛持续半闭
- 疑似吞入异物（无呼吸困难）
- 皮肤新增肿块（近2周出现）
- 排尿困难但仍有少量尿液（猫）

YELLOW 回复格式：
[TRIAGE:YELLOW]
🟡 **建议今日内就医**

症状需要兽医检查，暂时不危及生命，但应在 **24小时内** 就诊。

在等待就医期间：
• [1-2条针对性居家护理建议]
• 记录症状出现时间和发作频率，告知兽医

⚠️ 如出现以下情况请立即升级急诊：[列出1-2条恶化信号]

---
⚠️ *本建议仅供参考，不构成医疗诊断。*

---

## 🟢 GREEN — 居家观察（48小时内预约普通门诊）
适用情况：
- 单次呕吐后精神状态正常
- 轻微软便但有食欲
- 轻微抓挠无破皮
- 耳部轻微异味
- 饮水略多但无其他症状

GREEN 回复格式：
[TRIAGE:GREEN]
🟢 **可先居家观察**

目前情况相对稳定，建议：
• [1-2条家庭观察建议]
• 48小时内预约普通门诊检查

⚠️ 如出现以下情况请立即就医：[1-2条升级警戒信号]

---
⚠️ *本建议仅供参考，不构成医疗诊断。*

---

## 多轮问诊流程
- 描述不足时每次最多追问 2 个问题（种类/年龄？症状开始时间？精神状态？）
- 发现任何 RED 症状时：立即给出 RED 评估，跳过追问
- 对话结束时主动询问城市（若未提及）

## 禁止事项
- 不处理人类医疗话题
- 不保证任何诊断结论
- 不评判主人过去的护理决定
- 不推荐具体药物和剂量
```

---

## 六、Google Sheets 诊所数据库

### 表格结构（Sheet 名：`Clinics`）

| 列 | 字段名 | 示例（新西兰） | 说明 |
|----|--------|--------------|------|
| A | city | 奥克兰 | 城市（用于模糊匹配） |
| B | district | 北岸 | 区域（可选） |
| C | name | SPCA Auckland | 诊所名称 |
| D | phone | 09-xxx-xxxx | 电话 |
| E | address | 123 Great North Rd | 地址 |
| F | hours | 24小时 | 营业时间 |
| G | is_24h | TRUE | 布尔值（过滤用） |
| H | emergency | TRUE | 有急诊能力 |
| I | notes | 低价/免费 | 备注 |

### 初始数据收集方式
1. SPCA 官网（新西兰各分部）
2. Google Maps 搜索「24 hour vet Auckland/Christchurch」
3. 本地 Facebook 宠物群组问询
4. 各大学附属动物医院（通常收费较低）

### 配置步骤
1. Google Cloud Console → 创建 Service Account → 下载 JSON 密钥
2. 将 Sheet 共享给 Service Account 的 email（编辑权限）
3. n8n → Credentials → Google Sheets OAuth2 → 上传 JSON 密钥
4. 使用 n8n 内置 **Google Sheets 节点**（比 HTTP Request 更可靠）

---

## 七、前端关键代码

### 类型定义（`src/types/chat.types.ts`）
```typescript
export type TriageLevel = 'red' | 'yellow' | 'green' | 'unknown';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  triageLevel?: TriageLevel;
  timestamp: Date;
}

export interface ChatRequest {
  message: string;
  sessionId: string;  // UUID，持久化到 localStorage
}
```

### Zustand Store（`src/store/chatStore.ts`）
```typescript
// 关键：只持久化 sessionId 和 disclaimerAccepted，不持久化 messages（隐私保护）
const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [],
      sessionId: uuidv4(),
      isLoading: false,
      currentTriageLevel: 'unknown' as TriageLevel,
      disclaimerAccepted: false,
      // ...actions
    }),
    {
      name: 'pet-triage-storage',
      partialize: (state) => ({
        sessionId: state.sessionId,
        disclaimerAccepted: state.disclaimerAccepted,
        // messages 不持久化
      }),
    }
  )
);
```

### DisclaimerModal（`src/components/DisclaimerModal.tsx`）
关键交互逻辑：
- 全屏遮罩（`z-50`），背景完全不可交互
- 必须勾选复选框才能激活确认按钮
- 接受后存入 Zustand persist，刷新不再弹出
- 弹窗包含：工具说明 + 4条免责条款 + 数据收集告知

### TriageIndicator（`src/components/TriageIndicator.tsx`）
```tsx
// 🔴 RED 显示红色脉冲动画（animate-ping），YELLOW/GREEN 静态圆点
const CONFIG = {
  red:    { label: '🔴 立即急诊', pulse: true,  classes: 'bg-red-100 border-red-400 text-red-700' },
  yellow: { label: '🟡 今日就医', pulse: false, classes: 'bg-yellow-100 border-yellow-400 text-yellow-700' },
  green:  { label: '🟢 观察等候', pulse: false, classes: 'bg-green-100 border-green-400 text-green-700' },
};
```

---

## 八、NestJS 关键代码

### ChatLog Schema（`src/modules/chat/chat.schema.ts`）
```typescript
@Schema({ timestamps: true, collection: 'chat_logs' })
export class ChatLog {
  @Prop({ required: true, index: true }) sessionId: string;
  @Prop({ required: true, enum: ['user', 'assistant'] }) role: string;
  @Prop({ required: true }) content: string;
  @Prop({ enum: ['red','yellow','green','unknown'], default: 'unknown' }) triageLevel: string;
  @Prop() ip?: string;
}
```

### ChatService 核心逻辑（`src/modules/chat/chat.service.ts`）
```typescript
async sendMessage(dto: SendMessageDto, ip: string) {
  // 1. 记录用户消息到 MongoDB
  await this.chatLogModel.create({
    sessionId: dto.sessionId, role: 'user', content: dto.message, ip
  });

  try {
    // 2. 转发到 n8n 内网（35秒超时）
    const res = await firstValueFrom(
      this.httpService.post(
        this.n8nWebhookUrl,
        { chatInput: dto.message, sessionId: dto.sessionId },
        { timeout: 35000 }
      )
    );
    const { output, triageLevel } = res.data;

    // 3. 记录助手回复
    await this.chatLogModel.create({
      sessionId: dto.sessionId, role: 'assistant', content: output, triageLevel
    });

    return { reply: output, triageLevel, sessionId: dto.sessionId };

  } catch (err) {
    // 4. 记录错误，返回友好提示
    await this.chatLogModel.create({
      sessionId: dto.sessionId, role: 'assistant', content: 'SYSTEM_ERROR', triageLevel: 'unknown'
    });
    throw new HttpException('AI 服务暂时不可用', HttpStatus.SERVICE_UNAVAILABLE);
  }
}
```

### ChatController（`src/modules/chat/chat.controller.ts`）
```typescript
@Controller('chat')
export class ChatController {
  @Public()  // 复用 omniport 的 @Public 装饰器，跳过 JWT 验证
  @Post('message')
  @Throttle({ default: { limit: 10, ttl: 60000 } })  // 10次/分钟/IP
  async sendMessage(@Body() dto: SendMessageDto, @Ip() ip: string) {
    return this.chatService.sendMessage(dto, ip);
  }
}
```

### 环境变量（`backend/.env`）
```bash
NODE_ENV=production
PORT=3000
FRONTEND_URL=https://pettriage.yourdomain.com
CORS_ORIGINS=https://pettriage.yourdomain.com
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/pet_triage
N8N_WEBHOOK_URL=http://n8n:5678/webhook/pet-triage-chat  # Docker内网
THROTTLE_TTL=60000
THROTTLE_LIMIT=10
```

---

## 九、基础设施配置

### docker-compose.yml 关键改动（相对 omniport）
```yaml
services:
  backend1:
    image: pet-triage-backend:latest
    networks:
      - default
      - n8n_network  # 加入 n8n 所在 Docker network，实现内网通信

networks:
  default: {}
  n8n_network:
    external: true  # docker network ls 查看 n8n 容器所在 network 名称
```

### nginx.conf 关键改动（相对 omniport）
```nginx
# 1. 改域名（共2处）
server_name pettriage.yourdomain.com;

# 2. API location 加超时（Gemini 响应较慢）
location /api/ {
  proxy_pass http://backend_cluster;
  proxy_read_timeout 35s;   # ← 新增
  proxy_send_timeout 35s;   # ← 新增
  # 其余配置与 omniport 完全相同
}
```

### cd.yml GitHub Actions 改动（相对 omniport）
- 移除：`GOOGLE_CLIENT_ID/SECRET/CALLBACK_URL`、`JWT_ACCESS_EXPIRES_IN`、`AUTH_COOKIE_*`
- 新增：`N8N_WEBHOOK_URL`
- 修改：Health check URL 改为新域名

---

## 十、MVP 三周执行计划

### 第一周：n8n 核心工作流（不写代码，在 n8n 界面操作）

| Day | 任务 | 验证标准 |
|-----|------|---------|
| 1-2 | 创建 n8n 工作流，配置 Chat Trigger + Gemini AI，粘贴完整系统提示词 | 输入「狗狗抽搐」→ 回复含 [TRIAGE:RED] |
| 3 | 添加 IF 节点 + Error Trigger + 回退话术 | 断开 Gemini Key → 返回回退话术 |
| 4 | 创建 Google Sheet，填入10-20条诊所数据，配置 Service Account | Sheet 可读取，数据格式正确 |
| 5 | 添加 Google Sheets 节点，测试城市筛选 | 输入「在奥克兰，猫不吃东西」→ 返回奥克兰诊所列表 |

### 第二周：前端 + NestJS

| Day | 任务 | 验证标准 |
|-----|------|---------|
| 6-7 | `npm create vite@latest`，实现 DisclaimerModal + ChatWindow，直接调 n8n Webhook | 浏览器聊天正常，弹窗逻辑正确 |
| 8-9 | `nest new backend`，复制 omniport common/ 目录，创建 ChatModule | `/api/chat/message` 接口可调用 |
| 10 | NestJS 对接 n8n + MongoDB Atlas 日志 | 每次对话在 Atlas 产生2条记录 |
| 11 | 本地 docker compose up --build 验证全链路 | 全链路通，移动端适配正常 |

### 第三周：部署上线

| Day | 任务 | 验证标准 |
|-----|------|---------|
| 12 | 复制 omniport Dockerfiles，调整 docker-compose.yml（加 n8n_network）和 nginx.conf | docker compose up --build 本地成功 |
| 13 | EC2 手动 SSH 部署，certbot 申请新域名 SSL | HTTPS 可访问，证书有效 |
| 14 | 配置 GitHub Secrets，push main 触发 CD | CI/CD 自动部署成功，Health check 通过 |
| 15 | 找5位养宠物朋友测试，收集真实症状场景 | 收集≥10个测试案例，优化提示词 |

---

## 十一、验证方案（端到端测试）

### n8n 内置聊天测试
```
用例1 RED：「我的柯基3岁，突然倒地，全身抽搐」
期望：含[TRIAGE:RED]，回复包含「立即急诊」

用例2 YELLOW+诊所：「在奥克兰，猫昨晚开始不吃东西，吐了3次」
期望：含[TRIAGE:YELLOW][CITY:奥克兰]，回复含诊所名称和电话

用例3 GREEN：「狗今早吐了一次，现在精神很好还在玩」
期望：含[TRIAGE:GREEN]，建议观察

用例4 错误：断开Gemini API Key
期望：返回固定回退话术
```

### API 测试（curl）
```bash
curl -X POST https://pettriage.yourdomain.com/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message":"我的猫突然呼吸困难","sessionId":"test-uuid-1234"}'
# 期望: 200, { "triageLevel": "red", "reply": "..." }
```

### 限流测试
```bash
for i in {1..11}; do
  curl -s -o /dev/null -w "Request $i: %{http_code}\n" \
    -X POST https://pettriage.yourdomain.com/api/chat/message \
    -H "Content-Type: application/json" \
    -d '{"message":"test","sessionId":"test-1234"}'
done
# 期望: 前10次200，第11次429
```

### MongoDB 日志验证
```javascript
// 在 MongoDB Atlas Data Explorer 执行
db.chat_logs.find({ sessionId: "test-uuid-1234" }).sort({ createdAt: -1 })
// 期望: user记录 + assistant记录，助手记录含正确triageLevel
```

### 免责声明测试
1. 清除 localStorage → 刷新 → 弹窗出现，背景不可交互 ✓
2. 勾选复选框 → 确认按钮激活 → 点击 → 弹窗消失 ✓
3. 再次刷新 → 不再弹出 ✓

---

## 十二、关键技术注意事项

| 问题 | 解决方案 |
|------|---------|
| n8n 与 NestJS 网络互通 | 运行 `docker network ls` 查找 n8n 所在 network，在 docker-compose.yml 中声明 `external: true` 并让 backend1 加入该 network |
| Gemini 响应慢（最长20秒） | NestJS timeout: 35000，Nginx proxy_read_timeout 35s，前端显示 TypingDots |
| Session Memory 配置 | 使用 Window Buffer Memory（非 Simple Memory），Context Window Length = 10 |
| Gemini 免费层限额 | 1500次/天。每日在 MongoDB 统计 assistant 记录数，超1200次发邮件告警（n8n Schedule Trigger + 邮件节点） |
| 多轮对话连续性 | sessionId 存 localStorage，每次请求携带，n8n 的 Session Memory 按 sessionId 隔离对话 |
| 隐私保护 | Zustand persist 不持久化 messages，用户刷新后历史消失；数据库日志仅供运营分析 |

---

## 十三、后续迭代方向（上线后）

### 短期（上线后1个月）
- [ ] 用户反馈按钮（👍👎）→ 存 MongoDB，识别答得差的场景
- [ ] 扩展诊所数据库（基督城、惠灵顿、汉密尔顿）
- [ ] 诊所数据定期维护提醒（每季度检查电话/地址有效性）

### 中期（3个月）
- [ ] 接入 Telegram Bot（对新西兰华人社区更友好）
- [ ] A/B 测试不同版本提示词（随机分配 sessionId，对比有用率）
- [ ] 多语言支持（英文版本，覆盖非华语用户）

### 长期（6个月）
- [ ] 接入真实诊所预约 API（如 VetEnvoy、ezyVet）
- [ ] 症状照片上传（Gemini Vision 分析皮肤病/眼部问题）
- [ ] 移动端 App（复用现有 React Native dog_app 项目经验）

---

*计划生成日期：2026-05-27 | 基于 n8n v2.21.7 + omniport 部署经验*



---

接下来：
:Python + LLM API + agent 逻辑 + 生产工程。
模型层——就是你已经在碰的,调用大模型 API(Anthropic、OpenAI 等)。
编排层(agent 逻辑)——用 Python 写,或者用 LangGraph 这类框架管理 agent 的多步流程、工具调用、状态。这是你接下来几周的重点。
后端服务层——把你的 agent 包成一个能被访问的服务。Python 这边最主流的是 FastAPI(现代、快、自带 API 文档,做 AI 服务几乎是默认选择)。这一层取代你说的 Firebase Functions 那个角色,而且更通用、更主流。
数据层——存对话历史、用户数据、向量(给知识库用)。关系型数据常用 PostgreSQL,向量库常用 pgvector、Qdrant、Milvus。
部署层——用 Docker 把应用打包,这是现代部署的事实标准;再往上跑在云服务器或 Kubernetes 上。
这套(FastAPI + PostgreSQL + Docker)是当下 Python 后端 / AI 服务最主流、最不会过时的组合,学这个绝对不算捷径,是正道。
```
┌─────────────────────────────────────────────┐
│  第3层 · 编排与封装  (怎么交付出去)            │
│   ┌──────────────┐    ┌──────────────────┐  │
│   │ 可视化平台    │    │ 代码工程 ★你主攻  │  │
│   │ n8n / Coze   │    │ Python+FastAPI   │  │
│   │ 拖拽，看得见  │    │ +Docker，进生产  │  │
│   └──────────────┘    └──────────────────┘  │
├─────────────────────────────────────────────┤
│  第2层 · 应用逻辑  (LLM 这条线，从被动到主动)  │
│   ①直接问答 → ②多轮对话 → ③工具调用 → ④Agent  │
│   (你已会)    (下一步★)   (function    Loop   │
│                          calling)   (才叫agent)│
├─────────────────────────────────────────────┤
│  第1层 · 底层智能  (智能从哪来)                │
│   ┌──────────────┐    ┌──────────────────┐  │
│   │ 传统ML模型    │    │ 大语言模型 LLM    │  │
│   │ 小而专,自己训 │    │ 大而通用,调API    │  │
│   │ ★你在学的微软 │    │ 做agent用的脑子   │  │
│   │  ML课        │    │ Claude/GPT       │  │
│   └──────────────┘    └──────────────────┘  │
├─────────────────────────────────────────────┤
│  共享地基: numpy/pandas/matplotlib + 评估思维  │
│  (学ML练的,做agent照样用)                      │
└─────────────────────────────────────────────┘

```
