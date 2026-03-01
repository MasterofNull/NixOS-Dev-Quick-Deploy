import * as React from "react"
import { cn } from "@/lib/utils"

// Simple chart container components for Recharts
type ChartContainerProps = React.HTMLAttributes<HTMLDivElement> & {
  config?: Record<string, { label?: string; color?: string }>;
};

const ChartContainer = React.forwardRef<HTMLDivElement, ChartContainerProps>(
  ({ className, config: _config, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("w-full h-full", className)}
      {...props}
    />
  )
)
ChartContainer.displayName = "ChartContainer"

// Chart tooltip wrapper — accepts either children or a content element
const ChartTooltip = ({
  children,
  content,
}: {
  children?: React.ReactNode;
  content?: React.ReactNode;
}) => {
  return <>{content ?? children}</>
}

const ChartTooltipContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-lg border bg-background p-2 shadow-sm",
      className
    )}
    {...props}
  />
))
ChartTooltipContent.displayName = "ChartTooltipContent"

export { ChartContainer, ChartTooltip, ChartTooltipContent }
