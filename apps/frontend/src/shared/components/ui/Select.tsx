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
      className="bg-zinc-900 text-zinc-400 font-semibold"
    >
      {group.options.map((option) => (
        <option
          key={option.value}
          value={option.value}
          className="bg-zinc-900 text-zinc-100 font-normal"
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
      className={`w-full rounded-none border border-zinc-800 bg-zinc-900 px-3 py-2 font-sans text-sm text-zinc-300 focus:outline-none focus:border-zinc-400 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
      {...rest}
    >
      {groups ? groups.map(renderGroup) : options?.map(renderOption)}
    </select>
  );
};
