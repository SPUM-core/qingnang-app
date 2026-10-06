"""生成 frontend/src/types/templates.ts — 从后端 Pydantic 模型 auto-generate

用法:
  cd backend && python scripts/gen_ts_types.py

输出到: frontend/src/types/templates.ts
不手动编辑此 TS 文件 — 改模板模型后重新跑这个脚本。
"""
import json
import sys
import os

# 让脚本可以从 scripts/ 运行
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.templates import (
    AIResponseTemplate, ActionSuggestion, BriefCardFill,
    AddReminderParams, MarkLifeSignalParams, UpdateChiefComplaintParams, NavigateParams,
    _ACTION_PARAMS_MODELS, _ACTION_ICONS,
)

FRONTEND_TS = os.path.join(
    os.path.dirname(__file__), '..', '..', 'frontend', 'src', 'types', 'templates.ts'
)

# 每个 Pydantic model → TS interface 名
_PARAMS_MODELS = [
    ('AddReminderParams', AddReminderParams),
    ('MarkLifeSignalParams', MarkLifeSignalParams),
    ('UpdateChiefComplaintParams', UpdateChiefComplaintParams),
    ('NavigateParams', NavigateParams),
]

_OTHER_MODELS = [
    ('BriefCardFill', BriefCardFill),
    ('ActionSuggestion', ActionSuggestion),
]

# ── TS 类型映射 ──
def _py_type_to_ts(py: dict, name_hint: str = '') -> str:
    t = py.get('type', 'any')
    if t == 'string':
        return 'string'
    if t in ('integer', 'number'):
        return 'number'
    if t == 'boolean':
        return 'boolean'
    if t == 'array':
        return f"{_py_type_to_ts(py.get('items', {}))}[]"
    if t == 'object':
        return 'Record<string, any>'
    # 引用到自己定义的 interface
    if name_hint == 'brief_card':
        return 'BriefCardFill | null'
    if name_hint == 'suggested_actions':
        return 'ActionSuggestion[] | null'
    if name_hint == 'params':
        return 'Record<string, any>'
    return 'any'


def _gen_interface(name: str, model) -> str:
    s = model.model_json_schema()
    props = s.get('properties', {})
    required = set(s.get('required', []))
    lines = [f'export interface {name} {{']
    for k, v in props.items():
        ts = _py_type_to_ts(v, name_hint=k)
        opt = '' if k in required else '?'
        desc = v.get('description', '')
        if desc:
            # 截断过长的描述
            short = desc.replace('\n', ' ')[:80]
            lines.append(f'  /** {short} */')
        lines.append(f'  {k}{opt}: {ts};')
    lines.append('}')
    return '\n'.join(lines)


def main():
    out = []
    out.append('// Auto-generated from Pydantic models (backend/app/templates/ai_response.py)')
    out.append('// DO NOT EDIT MANUALLY — regenerate via: cd backend && python scripts/gen_ts_types.py')
    out.append('')

    # 1. Action Params 模型
    out.append('// ── Action Params Models ──')
    out.append('// Matches backend validate_action_params()')
    out.append('')
    for name, m in _PARAMS_MODELS:
        out.append(_gen_interface(name, m))
        out.append('')

    # ActionParams union
    out.append('export type ActionParams = '
               'AddReminderParams | MarkLifeSignalParams | UpdateChiefComplaintParams | NavigateParams | Record<string, any>;')
    out.append('')

    # 2. BriefCardFill + ActionSuggestion + AIResponseTemplate
    out.append('// ── Core Response Models ──')
    out.append('')
    for name, m in _OTHER_MODELS:
        out.append(_gen_interface(name, m))
        out.append('')

    out.append(_gen_interface('AIResponseTemplate', AIResponseTemplate))
    out.append('')

    # 3. Action Registry (icons)
    out.append('// ── Action Registry (mirrors backend _ACTION_ICONS) ──')
    out.append('')
    out.append('export type ActionId = ' + ' | '.join(f'"{k}"' for k in _ACTION_PARAMS_MODELS.keys()) + ';')
    out.append('')
    out.append('export const ACTION_ICONS: Record<ActionId, string> = '
               + json.dumps(_ACTION_ICONS, ensure_ascii=False, indent=2) + ';')
    out.append('')

    # 4. Execute API shapes
    out.append('// ── Execute API ──')
    out.append('')
    out.append('export interface ExecuteRequest {')
    out.append('  action_id: ActionId;')
    out.append('  params: ActionParams;')
    out.append('}')
    out.append('')
    out.append('export interface ExecuteResponse {')
    out.append('  ok: boolean;')
    out.append('  action_id: ActionId;')
    out.append('  label: string;')
    out.append('  result: Record<string, any>;')
    out.append('}')
    out.append('')

    # 5. Action Button shape
    out.append('// ── Action Button (frontend doAction 入参) ──')
    out.append('')
    out.append('export interface ActionButton {')
    out.append('  type: "navigate" | "api_call";')
    out.append('  action_id?: ActionId;')
    out.append('  params?: ActionParams;')
    out.append('  route?: string;')
    out.append('  label: string;')
    out.append('  icon?: string;')
    out.append('  priority?: "high" | "medium" | "low";')
    out.append('}')

    # 写文件
    os.makedirs(os.path.dirname(FRONTEND_TS), exist_ok=True)
    with open(FRONTEND_TS, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))

    print(f'✅ Generated {os.path.abspath(FRONTEND_TS)}')
    print(f'   Interfaces: {len(_PARAMS_MODELS) + len(_OTHER_MODELS) + 1}')
    print(f'   ActionIds: {list(_ACTION_PARAMS_MODELS.keys())}')


if __name__ == '__main__':
    main()
