export interface FilterOption<TValue extends string = string> {
  value: TValue
  label: string
}

export function buildFilterOptions<TValue extends string>(
  values: Iterable<TValue>,
  getLabel: (value: TValue) => string,
): FilterOption<TValue>[] {
  const seen = new Set<TValue>()
  const options: FilterOption<TValue>[] = []

  for (const value of values) {
    if (seen.has(value)) continue
    seen.add(value)
    options.push({
      value,
      label: getLabel(value),
    })
  }

  return options
}

export function labelForFilterValue<TValue extends string>(
  options: readonly FilterOption<TValue>[],
  value: string,
  fallback: string,
): string {
  const match = options.find((option) => option.value === value)
  return match?.label ?? fallback
}
