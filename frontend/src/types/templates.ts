// Auto-generated from Pydantic models (backend/app/templates/ai_response.py)
// DO NOT EDIT MANUALLY — regenerate via: cd backend && python scripts/gen_ts_types.py

// ── Action Params Models ──
// Matches backend validate_action_params()

export interface AddReminderParams {
  /** 提醒内容，如'今晚22:30前入睡' */
  content: string;
}

export interface MarkLifeSignalParams {
  /** 信号标签：sleep/appetite/bowel/mood/energy/thirst/sweat/skin/breath/other */
  tag: string;
  /** 具体描述，如'入睡困难'、'大便偏干' */
  label: string;
}

export interface UpdateChiefComplaintParams {
  /** 用户的主要不适主诉 */
  chief_complaint: string;
}

export interface NavigateParams {
  /** 跳转路径：/collect/ppg /notifications /case /discover /shop */
  route: string;
}

export type ActionParams = AddReminderParams | MarkLifeSignalParams | UpdateChiefComplaintParams | NavigateParams | Record<string, any>;

// ── Core Response Models ──

export interface BriefCardFill {
  /** 是否展示卡片（用户问了宜忌/饮食时为 true） */
  show?: boolean;
  /** 干支宜忌的人话解读 */
  anchor_note?: any;
  /** 重点推荐的那道菜 */
  food_highlight?: any;
}

export interface ActionSuggestion {
  /** 可用值见 system prompt 里的 action 列表 */
  action_id: string;
  /** 按 action_id 的模板填字段 */
  params?: Record<string, any>;
  /** 展示给用户的按钮文案，如留空后端补默认 */
  label?: any;
}

export interface AIResponseTemplate {
  /** 自然语言回复，必填 */
  reply: string;
  /** 想展示今日宜忌卡片时填 */
  brief_card?: BriefCardFill | null;
  /** 建议执行的操作 */
  suggested_actions?: ActionSuggestion[] | null;
}

// ── Action Registry (mirrors backend _ACTION_ICONS) ──

export type ActionId = "add_reminder" | "mark_life_signal" | "update_chief_complaint" | "navigate";

export const ACTION_ICONS: Record<ActionId, string> = {
  "add_reminder": "🔔",
  "mark_life_signal": "✅",
  "update_chief_complaint": "📝",
  "navigate": "→"
};

// ── Execute API ──

export interface ExecuteRequest {
  action_id: ActionId;
  params: ActionParams;
}

export interface ExecuteResponse {
  ok: boolean;
  action_id: ActionId;
  label: string;
  result: Record<string, any>;
}

// ── Action Button (frontend doAction 入参) ──

export interface ActionButton {
  type: "navigate" | "api_call";
  action_id?: ActionId;
  params?: ActionParams;
  route?: string;
  label: string;
  icon?: string;
  priority?: "high" | "medium" | "low";
}