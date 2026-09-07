export interface CoverImageUploaderProps {
  value?: string | null;
  onChange: (url: string | null) => void;
  label?: string;
  description?: string;
  disabled?: boolean;
  className?: string;
}
