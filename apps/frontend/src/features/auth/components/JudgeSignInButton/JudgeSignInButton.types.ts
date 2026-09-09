export interface JudgeSignInButtonProps {
  onClick: () => void;
  isPending?: boolean;
  disabled?: boolean;
  judgeEmail?: string;
  judgePassword?: string;
}
