import React from "react";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  options: SelectOption[];
}

export const Select: React.FC<SelectProps> = ({
  options,
  className = "",
  ...rest
}) => {
  return (
    <select
      className={`w-full rounded-none border border-zinc-800 bg-zinc-900 px-3 py-2 font-sans text-sm text-zinc-300 focus:outline-none focus:border-zinc-400 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
      {...rest}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
};
