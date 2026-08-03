# Agent State Sync

一个面向 Codex、Claude、OpenClaw、Antigravity、WorkBuddy 和其他 Agent
的安全状态同步 Skill。

把这个 GitHub 首页链接交给 Agent，它应先阅读本页，再阅读
[SKILL.md](SKILL.md) 和需要的参考文件，最后根据用户明确授权执行安装或同步。

## 给 Agent 的入口规则

如果用户只提供了这个 GitHub 首页链接，请按以下顺序工作：

1. 阅读本页、[SKILL.md](SKILL.md)、[references/safety-policy.md](references/safety-policy.md)
   和 [references/state-schema.md](references/state-schema.md)。
2. 把本仓库视为公开的 Skill 代码，不把它当作用户的个人状态仓库。
3. 先只读检查本机已安装的 Skill、运行时、插件、路径和 GitHub 认证状态。
4. 展示安装计划和将要写入的路径，等待用户确认后再安装或修改配置。
5. 同一台电脑只保留一份 Skill 仓库和一份私有状态仓库本地镜像。
6. 优先复用已有搜索路径、共享目录或可追踪软链接，不复制运行时、缓存、
   虚拟环境、插件缓存和完整 Agent 状态目录。
7. 只有在用户明确提供或确认私有状态仓库后，才执行状态同步。
8. 安装、插件变更、认证、模型切换、外部写入、提交和推送都需要明确授权。

不得因为用户提供了本页链接，就自动登录、安装第三方依赖、复制凭据、
覆盖 Agent 配置或推送用户状态。

## 设计目标

本项目由两部分组成：

~~~text
公开仓库：xybyx/agent-state-sync
  Skill、脚本、适配器契约、安全规则和示例

私有仓库：用户自己的 agent-state
  模型路由、协同规则、偏好、Skill/插件清单和精选项目记忆
~~~

公开仓库永远不应包含个人模型配置、OAuth、API Key、浏览器会话、
项目数据库或完整的 Agent 主目录。

## 安装 Skill

### 每台电脑只克隆一份

要求 Git 和 Python 3.9 或更高版本。推荐在每台电脑使用一个共享目录：

~~~bash
mkdir -p ~/.agent-state-sync
git clone https://github.com/xybyx/agent-state-sync.git \
  ~/.agent-state-sync/skill
~~~

升级时：

~~~bash
git -C ~/.agent-state-sync/skill pull --ff-only
~~~

不要为 Codex、Claude、Antigravity 和 WorkBuddy 分别克隆四份。

### 让多个 Agent 复用同一份 Skill

在确认目标目录不存在后，再创建可追踪软链接或使用 Agent 支持的共享
Skill 搜索路径：

~~~bash
ln -s ~/.agent-state-sync/skill ~/.codex/skills/agent-state-sync
ln -s ~/.agent-state-sync/skill ~/.claude/skills/agent-state-sync
ln -s ~/.agent-state-sync/skill ~/.agents/skills/agent-state-sync
~~~

如果目标路径已经存在，不要覆盖。先检查它是否已经指向相同仓库。
如果某个 Agent 不支持软链接或共享搜索路径，先报告空间例外，不要静默复制。

Antigravity 和 WorkBuddy 的安装路径可能随版本变化。必须先检测版本、
控制面、Skill 搜索路径和能力，不得假设固定目录或 CLI 一定存在。

## 私有状态仓库

状态仓库必须使用私有 GitHub 仓库或用户明确批准的等价安全存储。
可以用本仓库的示例初始化：

~~~bash
AGENT_SYNC_OWNER=your-github-owner
AGENT_SYNC_STATE_NAME=my-agent-state
cd ~/.agent-state-sync
gh repo create "$AGENT_SYNC_OWNER/$AGENT_SYNC_STATE_NAME" --private --clone
cp -R ~/.agent-state-sync/skill/examples/state-repo/. \
  ~/.agent-state-sync/"$AGENT_SYNC_STATE_NAME"/
git -C ~/.agent-state-sync/"$AGENT_SYNC_STATE_NAME" add .
git -C ~/.agent-state-sync/"$AGENT_SYNC_STATE_NAME" commit \
  -m "Initialize private agent state"
git -C ~/.agent-state-sync/"$AGENT_SYNC_STATE_NAME" push -u origin main
~~~

每台电脑只需要一份私有状态仓库本地镜像：

~~~bash
git clone "https://github.com/$AGENT_SYNC_OWNER/$AGENT_SYNC_STATE_NAME.git" \
  ~/.agent-state-sync/state
~~~

用户没有提供私有状态仓库时，Agent 应该询问，而不是创建一个公开仓库
或把状态写入本项目。

## 状态内容

私有仓库中的 state/shared/ 可以保存：

- models.json：逻辑模型名、供应商、fallback 和 auth_ref；
- collaboration.json：lead Agent、精确模型、任务边界、交接、重试和审查；
- preferences.json：语言、表达方式、格式和工作偏好；
- skills.lock.json：Skill 来源、版本、哈希、审查状态和复用方式；
- plugins.lock.json：插件来源、版本、安装状态和审批状态；
- memory/：精选决策和项目上下文。

state/machines/ 保存机器覆盖层、批准的路径和空间例外。

state/agents/ 保存 Agent 适配器能力和安全的渲染目标。

## 绝不写入或同步的内容

- API Key、OAuth Token、密码、Cookie、Session、私钥；
- .env、credentials、secrets 和认证配置；
- SQLite、WAL、SHM、浏览器 Profile、活动 Socket；
- node_modules、虚拟环境、包缓存、模型缓存、插件缓存；
- 完整的 ~/.codex、~/.claude、~/.openclaw 或其他 Agent 状态目录；
- 未经适配器拆分的原生配置文件；
- 任意指向批准目录之外的软链接。

auth_ref 只能表示凭据来源，例如：

~~~json
{
  "auth_ref": "keychain://provider/default"
}
~~~

不得把真实 Token 放进 JSON、Markdown、提交记录或终端输出。

## 最小占用空间原则

所有同步操作遵循以下优先级：

~~~text
复用已有安装
  > 共享搜索路径
  > 可追踪软链接
  > 每台电脑一份本地克隆
  > 经用户确认并记录理由的复制
~~~

具体约束：

- 同一台电脑只保留一份状态仓库镜像；
- 同一台电脑的所有 Agent 共用一份 Skill 仓库；
- 已有 Python、Node、CLI、运行时和本地服务优先复用；
- 不复制 Skill、插件缓存、模型缓存、浏览器状态和虚拟环境；
- 版本冲突或安全隔离需要副本时，必须写入机器空间例外；
- space-audit 只报告重复内容，不自动删除。

跨电脑无法避免每台电脑至少保留一份必要的本地镜像；优化目标是每台
电脑一份、每个 Agent 不再额外复制。

## v0.1 使用流程

脚本位于：

~~~text
scripts/agent_state_sync.py
~~~

先定义本机路径：

~~~bash
AGENT_SYNC_SKILL=~/.agent-state-sync/skill
AGENT_SYNC_STATE=~/.agent-state-sync/state
~~~

### 1. 校验状态仓库

~~~bash
python3 "$AGENT_SYNC_SKILL/scripts/agent_state_sync.py" doctor \
  --state-repo "$AGENT_SYNC_STATE"
~~~

### 2. 只读盘点 Agent

Codex 示例：

~~~bash
AGENT_SYNC_MACHINE=macbook-pro
AGENT_SYNC_AGENT=codex
python3 "$AGENT_SYNC_SKILL/scripts/agent_state_sync.py" inventory \
  --root ~/.codex/AGENTS.md \
  --root ~/.codex/skills \
  --machine "$AGENT_SYNC_MACHINE" \
  --agent "$AGENT_SYNC_AGENT" \
  --output /tmp/codex-inventory.json
~~~

Claude、Antigravity 和 WorkBuddy 必须替换为实际确认过的路径和 Agent ID。
盘点会跳过敏感文件、缓存、数据库、虚拟环境和软链接，不会复制文件。

### 3. 生成漂移计划

~~~bash
python3 "$AGENT_SYNC_SKILL/scripts/agent_state_sync.py" plan \
  --state-repo "$AGENT_SYNC_STATE" \
  --inventory /tmp/codex-inventory.json \
  --machine "$AGENT_SYNC_MACHINE" \
  --agent "$AGENT_SYNC_AGENT" \
  --output /tmp/codex-plan.json
~~~

### 4. 用户确认后记录机器基线

~~~bash
python3 "$AGENT_SYNC_SKILL/scripts/agent_state_sync.py" snapshot \
  --state-repo "$AGENT_SYNC_STATE" \
  --inventory /tmp/codex-inventory.json \
  --machine "$AGENT_SYNC_MACHINE" \
  --confirm
~~~

然后提交私有状态仓库：

~~~bash
git -C "$AGENT_SYNC_STATE" add state/machines
git -C "$AGENT_SYNC_STATE" commit -m "Record machine baseline"
git -C "$AGENT_SYNC_STATE" push
~~~

### 5. 在另一台电脑拉取

~~~bash
git -C "$AGENT_SYNC_STATE" pull --ff-only
python3 "$AGENT_SYNC_SKILL/scripts/agent_state_sync.py" doctor \
  --state-repo "$AGENT_SYNC_STATE"
~~~

然后用新电脑自己的 machine-id 和 Agent ID 重新执行盘点和计划。

## 当前版本的真实边界

v0.1 已经支持：

- 私有状态仓库的 schema 校验；
- secret scan；
- Agent/机器文件盘点；
- 基线差异计划；
- 重复文件和潜在空间占用审计；
- 最小空间策略和适配器契约。

v0.1 尚未自动执行：

- 将 models.json 写回每个 Agent 的原生配置；
- 自动安装第三方 Skill 或插件；
- 迁移 OAuth、Keychain、浏览器会话或本地数据库；
- 把原始聊天记录自动转换为项目记忆；
- 自动覆盖 Antigravity 或 WorkBuddy 的未知配置路径。

Agent 不得把 plan 或 snapshot 报告为“所有 Agent 已完成同步”。
真正写入原生配置必须由已审查的适配器完成，并在用户确认后执行。

## 适配器规则

### Codex

使用明确批准的全局规则、Skill 搜索路径和精选项目记忆。不要复制完整
的 .codex 目录。

### Claude

只映射已确认的指令文件、Skill 路径和可迁移偏好。保留账号和运行时状态。

### OpenClaw

只同步拆分后的安全模型字段、规则和精选记忆。不要复制认证文件、
插件数据库或完整 openclaw.json。

### Antigravity

先探测版本、Skill 搜索路径、模型和写入能力。没有安全写入接口时，
只生成手动计划，不伪装成已应用。

### WorkBuddy

不要假设 CLI、固定目录或统一插件结构存在。GUI/账号/缓存/活动运行时
保持本地；无法安全写入时只返回盘点和手动计划。

## 安全和来源审查

- 第三方 Skill 和插件必须锁定来源、版本和内容哈希；
- 不要因为锁文件里出现安装器，就自动运行安装器；
- 不执行状态仓库中未经审查的命令；
- 公开仓库只包含 Skill 代码和示例；
- 私有状态仓库的每次变更都应在提交前做 secret scan；
- git push、认证、插件安装和外部写入必须由用户明确授权。

## 相关文件

- [Skill instructions](SKILL.md)
- [State schema](references/state-schema.md)
- [Safety policy](references/safety-policy.md)
- [Adapter contract](references/adapter-contract.md)
- [Conflict resolution](references/conflict-resolution.md)
- [Antigravity adapter notes](references/adapters/antigravity.md)
- [WorkBuddy adapter notes](references/adapters/workbuddy.md)
- [CLI](scripts/agent_state_sync.py)
