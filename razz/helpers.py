import re

class PathPattern:
  def __init__(self, pattern: str) -> None:
    pattern = pattern.rstrip("/")
    param_ranges: list[tuple[int, int]] = []
    param_search_start = 0
    while (param_start := pattern.find("{", param_search_start)) != -1:
      param_end = pattern.find("}", param_start)
      if param_end == -1: raise ValueError("Invalid pattern. Expected closing brace after opening brace.")
      param_search_start = param_end
      param_ranges.append((param_start, param_end))

    param_name_regex = re.compile("^[a-zA-Z0-9_]*\\*?$")

    self.parts: list[str] = []
    self.params: list[tuple[str|None,bool]] = []
    part_start = 0
    for ps, pe in param_ranges:
      self.parts.append(pattern[part_start:ps])

      param_txt = pattern[ps+1:pe].strip()
      if not param_name_regex.match(param_txt): raise ValueError("Invalid parameter name.")
      if param_txt.endswith("*"): self.params.append((param_txt[:-1] or None, True))
      else: self.params.append((param_txt or None, False))

      part_start = pe + 1

    self.parts.append(pattern[part_start:])

    for part in self.parts:
      if "}" in part: raise ValueError("Invalid pattern. Found closing brace without an opening brace.")

  def construct(self, params: dict[str, str], default_value: str | None = None) -> str:
    param_parts = []
    for param_name, param_allow_slash in self.params:
      v = params.get(param_name, default_value)
      if v is None: raise ValueError("Param can not be None!")
      if not param_allow_slash and "/" in v: raise ValueError("Found flash in param name, which is not allowed!")
      param_parts.append(v)
    result_parts = []
    for idx in range(len(self.params)):
      result_parts.append(self.parts[idx])
      result_parts.append(param_parts[idx])
    result_parts.append(self.parts[-1])
    return "".join(result_parts)

  def match(self, path: str) -> dict[str,str] | None:
    # path = path.rstrip("/")
    if len(self.parts) == 1:
      return {} if path == self.parts[0] else None

    params: dict[str, str] = {}
    current_index = 0
    for idx in range(0, len(self.parts) - 1):
      part1 = self.parts[idx]
      part2 = self.parts[idx + 1]
      param_name, param_allow_slash = self.params[idx]

      part1_len = len(part1)
      if path[current_index:current_index + part1_len] != part1: return None

      current_index += part1_len
      if part2 == "" and idx == len(self.parts) - 2:
        param_val = path[current_index:]
      else:
        part2_start = path.find(part2, current_index)
        if part2_start == -1: return None
        param_val = path[current_index:part2_start]
      current_index += len(param_val)
      if "/" in param_val and not param_allow_slash: return None
      if param_name is not None: params[param_name] = param_val
    return params
