def class_map(map: dict[str, bool]):
  return " ".join([ k for k, v in map.items() if v ])
