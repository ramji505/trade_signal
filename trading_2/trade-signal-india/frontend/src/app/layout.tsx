import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TradeSignal India — Private NIFTY 50 Intraday Signal App",
  description: "Private trading decision-support web application for NIFTY 50 intraday analysis.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="antialiased bg-slate-950 text-slate-100 min-h-screen" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
