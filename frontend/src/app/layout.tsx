import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "./components/sidebar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "AgentOS",
  description: "Production-grade local-first AI agent platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="bg-slate-950 text-slate-100 min-h-screen flex font-sans antialiased">
        <Sidebar />
        <main className="flex-1 overflow-auto h-screen">{children}</main>
      </body>
    </html>
  );
}
