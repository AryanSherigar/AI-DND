import React from "react";

export type SeparatorProps = React.HTMLAttributes<HTMLHRElement>;

export const Separator: React.FC<SeparatorProps> = ({
  className = "",
  ...rest
}) => {
  return (
    <hr className={`border-t border-zinc-800 ${className}`} {...rest} />
  );
};
