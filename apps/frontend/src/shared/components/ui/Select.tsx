import React from "react";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectOptionGroup {
  label: string;
  options: SelectOption[];
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  options?: SelectOption[];
  groups?: SelectOptionGroup[];
}

function renderGroup(group: SelectOptionGroup) {
  return (
    <optgroup
      key={group.label}
      label={group.label}
      className="bg-surface-raised font-semibold text-content-muted"
    >
      {group.options.map((option) => (
        <option
          key={option.value}
          value={option.value}
          className="bg-surface-raised font-normal text-content"
        >
          {option.label}
        </option>
      ))}
    </optgroup>
  );
}

function renderOption(option: SelectOption) {
  return (
    <option key={option.value} value={option.value}>
      {option.label}
    </option>
  );
}

export const Select: React.FC<SelectProps> = ({
  options,
  groups,
  className = "",
  ...rest
}) => {
  return (
    <select
      className={`w-full rounded-md border border-border-subtle bg-surface-inset px-3 py-2 font-sans text-sm text-content transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
      {...rest}
    >
      {groups ? groups.map(renderGroup) : options?.map(renderOption)}
    </select>
  );
};
