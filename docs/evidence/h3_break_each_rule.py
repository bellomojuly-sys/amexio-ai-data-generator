"""H3: break one rule at a time (contract §5 and plot.py) and record which tests fail."""
import subprocess, sys, pathlib
W = pathlib.Path(sys.argv[1])
C, P = "pipeline/contracts.py", "pipeline/plot.py"
M = [
 ("C1 max 10 slots", C, "slots: list[Slot] = Field(min_length=1, max_length=10)", "slots: list[Slot] = Field(min_length=1, max_length=11)"),
 ("C2 at least 1 slot", C, "slots: list[Slot] = Field(min_length=1, max_length=10)", "slots: list[Slot] = Field(min_length=0, max_length=10)"),
 ("C3 slot key format S01", C, 'SlotKey = Annotated[str, Field(pattern=r"^S\\d{2}$")]', "SlotKey = str"),
 ("C4 slot keys unique", C, '        _unique((s.slot for s in self.slots), f"employee {self.employee_number}: slot")\n', ""),
 ("C5 no date on a slot", C, "class _Slot(_In):\n    slot: SlotKey\n", "class _Slot(_In):\n    slot: SlotKey\n    date: str | None = None\n"),
 ("C6 no participant on a slot", C, "class _Slot(_In):\n    slot: SlotKey\n", "class _Slot(_In):\n    slot: SlotKey\n    signed_by: str | None = None\n"),
 ("C7 no ID on a slot", C, "class _Slot(_In):\n    slot: SlotKey\n", "class _Slot(_In):\n    slot: SlotKey\n    event_id: str | None = None\n"),
 ("C8 rating closed list", C, "    rating: Rating\n", "    rating: str\n"),
 ("C9 termination reason closed list", C, "    reason: TerminationReason\n", "    reason: str\n"),
 ("C10 change kind closed list", C, "    change: ChangeKind\n", "    change: str\n"),
 ("C11 promotion needs newPosition", C, 'if self.change == "promotion" and not self.new_position:', "if False:"),
 ("C12 newPosition only on promotion", C, 'if self.change != "promotion" and self.new_position:', "if False:"),
 ("C13 durationDays <= 5", C, "duration_days: int = Field(ge=1, le=5)", "duration_days: int = Field(ge=1, le=6)"),
 ("C14 durationDays >= 1", C, "duration_days: int = Field(ge=1, le=5)", "duration_days: int = Field(ge=0, le=5)"),
 ("C15 one termination", C, "if len(ends) > 1:", "if False:"),
 ("C16 nothing after termination", C, "if ends and ends[0] != len(self.slots) - 1:", "if False:"),
 ("C17 one outline per employee", C, '        _unique((o.employee_number for o in self.outlines), "employeeNumber")\n', ""),
 ("C18 hire is not a slot", C, '    type: Literal["absence"]\n', '    type: Literal["absence", "hire"]\n'),
 ("C19 at least one outline", C, "outlines: list[CaseOutline] = Field(min_length=1)", "outlines: list[CaseOutline]"),
 ("P1 appraisal only while employed", P, "if hire < dt.date(y, 6, 30) <= as_of]", "if dt.date(y, 6, 30) <= as_of]"),
 ("P2 at most 4 appraisals", P, "MAX_APPRAISALS = 4", "MAX_APPRAISALS = 40"),
 ("P3 permanent only after a year", P, 'job.contract_type == "Temporary" and years >= 1', 'job.contract_type == "Temporary" and years >= 0'),
 ("P4 promotion only after Exceeds", P, 'ratings[-1] == "Exceeds expectations"', 'ratings[-1] != "Below expectations"'),
 ("P5 promotion to non-manager", P, "if not p.is_manager_role and p.salary_max > current.salary_max]", "if p.salary_max > current.salary_max]"),
 ("P6 promotion to better-paid", P, "if not p.is_manager_role and p.salary_max > current.salary_max]", "if not p.is_manager_role and p.title != title]"),
 ("P7 training only with provider", P, "if config.company.training_provider else 0", "if True else 0"),
 ("P8 medical check after 2 years", P, "    if years >= 2:\n", "    if years >= 0:\n"),
 ("P9 new hire gets one slot", P, "    if not slots:\n", "    if False:\n"),
 ("P10 drop oldest appraisal first", P, '        oldest = next(i for i, s in enumerate(slots) if s["type"] == "appraisal")', "        oldest = len(slots) - 1"),
 ("P11 same seed same plot", P, "outline_case(case, config, random.Random(rng.random()))", "outline_case(case, config, random.Random())"),
 ("P12 duration 1-5 picked", P, "rng.randint(1, 5)", "rng.randint(4, 9)"),
 ("P13 salary review after a year", P, "    if years >= 1:\n        slots.append({\"type\": \"contract_change\", \"change\": \"salary_review\"})", "    if years >= 0:\n        slots.append({\"type\": \"contract_change\", \"change\": \"salary_review\"})"),
]
for name, f, old, new in M:
    path = W / f; src = path.read_text()
    if src.count(old) != 1:
        print(f"{name}: PATTERN COUNT {src.count(old)}"); continue
    path.write_text(src.replace(old, new))
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "pipeline"], cwd=W, capture_output=True, text=True, env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
    path.write_text(src)
    import re; failed = re.findall(r"^(?:FAILED|ERROR) \S+?::(\S+)", r.stdout, re.M)
    print(f"{name}: {'CAUGHT by ' + ', '.join(failed) if failed else 'NOT CAUGHT'}")
