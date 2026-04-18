import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { CommandBar } from "@/components/ui/command-bar";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AgentOS | Debugger",
  description: "Agent Orchestration and Evaluation",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark overflow-hidden">
      <body className={`${inter.className} bg-[#0A0A0C] text-[#E4E4E5] antialiased selection:bg-indigo-500/30 overflow-hidden`}>
        <Providers>
          <div className="flex h-screen w-full">
            <Sidebar />
            <main className="flex-1 flex flex-col min-w-0 border-l border-[#222224] bg-[#0F0F12]">
              {children}
            </main>
          </div>
          <CommandBar />
        </Providers>
      </body>
    </html>
  );
}
