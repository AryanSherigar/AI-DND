import React from "react";

export type CardProps = React.HTMLAttributes<HTMLDivElement>;

export const Card: React.FC<CardProps> = ({
  className = "",
  children,
  ...rest
}) => {
  return (
    <div
      className={`rounded-none border border-zinc-800 bg-zinc-950 p-4 ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
};
