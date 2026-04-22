import { redirect } from "next/navigation";

export default async function CategoryPage({
  params,
}: {
  params: Promise<{ category_id: string }>;
}) {
  const { category_id } = await params;
  redirect(`/storefront/vg?category=${category_id}`);
}
