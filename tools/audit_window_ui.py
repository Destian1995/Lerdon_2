"""Inventory game popup factories and the non-modal areas covered by the theme."""
import ast
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
windows = []
sources = []
for path in sorted(ROOT.rglob('*.py')):
    relative = path.relative_to(ROOT)
    if any(part.startswith('.') or part in ('old', 'tests', 'tools', '__pycache__') for part in relative.parts):
        continue
    tree = ast.parse(path.read_text(encoding='utf-8'))
    sources.append((relative, tree))

# Collect subclasses before inspecting callers in other modules.
popup_names = {'Popup', 'ThemedPopup'}
for relative, tree in sources:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'kivy.uix.popup':
            popup_names.update(alias.asname or alias.name for alias in node.names if alias.name == 'Popup')
        if isinstance(node, ast.ClassDef) and any(isinstance(base, ast.Name) and base.id in popup_names for base in node.bases):
            popup_names.add(node.name)
for relative, tree in sources:
    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.scope = []
        def visit_FunctionDef(self, node):
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()
        def visit_ClassDef(self, node):
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id in popup_names:
                title = next((kw.value for kw in node.keywords if kw.arg == 'title'), None)
                windows.append(dict(file=str(relative).replace('\\', '/'), line=node.lineno,
                                    scope='.'.join(self.scope), factory=node.func.id,
                                    title=title.value if isinstance(title, ast.Constant) else '<dynamic>'))
            self.generic_visit(node)
    Visitor().visit(tree)
report = dict(total_factories=len(windows), popup_theme='window_theme.install_window_theme → Popup.open',
              responsive_layout='responsive_ui.WindowFlow for legacy and custom Popup content',
              layout_rules=['text-aware minimum heights', '48dp action height', 'stacked action rows',
                            'scrollable overflow', 'viewport limits and rotation'],
              non_modal=['economic.start_economy_mode', 'politic.start_politic_mode',
                         'game_process.GameScreen.game_area', 'ui_components.DiplomacyMessagePopup'],
              custom_chrome=['strategy_ui.build_city_window', 'recruitment_ui.RecruitmentSession',
                             'battle_ui.BattleViewer', 'battle_ui.BattleReport'],
              by_file=dict(Counter(item['file'] for item in windows)), windows=windows)
output = ROOT / 'assets/window-style-audit.json'
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"{len(windows)} popup factories in {len(report['by_file'])} files")
