import "@/styles/globals.css";

import type { Metadata } from "next";
import { Roboto } from "next/font/google";

import { AppShell } from "@/components/robot/app-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { KeyboardController } from "@/robot/keyboard";

const roboto = Roboto({ subsets: ["latin", "vietnamese"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Mecanum - Bảng điều khiển",
  description: "Điều khiển và giám sát robot Mecanum theo thời gian thực",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="vi"
      className={cn("h-full", "antialiased", "font-sans", roboto.variable)}
    >
      <body className="min-h-full">
        <TooltipProvider>
          <KeyboardController />
          <AppShell>{children}</AppShell>
        </TooltipProvider>
      </body>
    </html>
  );
}
