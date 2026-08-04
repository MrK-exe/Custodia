import { notFound } from "next/navigation";
import { isLang } from "@/lib/dict";
import AccountView from "@/components/AccountView";

// Static demo account page. No server data read, so it exports cleanly under
// `output: export` for both statically-generated langs (ar/en).
export default async function AccountPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  return <AccountView lang={lang} />;
}
