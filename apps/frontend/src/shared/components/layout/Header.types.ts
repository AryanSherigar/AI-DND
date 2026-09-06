import { UserResponse } from "@/features/auth/types/auth.types";

export type HeaderVariant = "default" | "landing";

export interface HeaderProps {
  variant?: HeaderVariant;
}

export interface UserDropdownProps {
  user: UserResponse;
  onLogout: () => void;
}
