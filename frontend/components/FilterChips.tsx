import Link from "next/link";

/**
 * A group of chips for choosing one value (a position, availability, a view, a page of a section).
 * Buttons with aria-pressed by default; with `hrefFor` they are links to real pages (the open one
 * is aria-current) so the choice has its own address. The same look and keyboard behaviour on
 * every tab.
 */
export default function FilterChips<T extends string>({
  label,
  options,
  value,
  onChange,
  hrefFor,
}: {
  label: string;
  options: readonly { value: T; label: string }[];
  value: T;
} & (
  | { onChange: (value: T) => void; hrefFor?: undefined }
  | { hrefFor: (value: T) => string; onChange?: undefined }
)) {
  if (hrefFor) {
    return (
      <nav className="players-filter" aria-label={label}>
        {options.map((option) => (
          <Link
            key={option.value}
            href={hrefFor(option.value)}
            className="filter-chip"
            aria-current={option.value === value ? "page" : undefined}
          >
            {option.label}
          </Link>
        ))}
      </nav>
    );
  }
  return (
    <div className="players-filter" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className="filter-chip"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
