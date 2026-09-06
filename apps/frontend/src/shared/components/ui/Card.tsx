import React from "react";

export type CardProps = React.HTMLAttributes<HTMLDivElement>;

export const Card: React.FC<CardProps> = ({
  className = "",
  children,
  ...rest
}) => {
  return (
    <div
      className={`rounded-lg border border-border-subtle bg-surface-raised p-4 ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
};
