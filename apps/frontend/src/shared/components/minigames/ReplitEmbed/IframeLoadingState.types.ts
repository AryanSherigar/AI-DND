export interface IframeLoadingStateProps {
  isTimedOut: boolean;
  canRetry: boolean;
  onRetry: () => void;
}
