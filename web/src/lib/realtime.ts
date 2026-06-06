/**
 * Supabase Realtime subscription for shopping_items.
 * Approved FR-023 infrastructure exception: Realtime subscriptions bypass the FastAPI REST layer.
 * All CRUD operations still go through /api/v1/* endpoints.
 */
import type { RealtimePostgresChangesPayload } from "@supabase/supabase-js";
import { createAuthBrowserClient } from "@/lib/supabase";

export type ShoppingRealtimePayload = RealtimePostgresChangesPayload<Record<string, unknown>>;

export function subscribeToShopping(
  groupId: string,
  onPayload: (payload: ShoppingRealtimePayload) => void
): () => void {
  const supabase = createAuthBrowserClient();

  const channel = supabase
    .channel(`shopping:${groupId}`)
    .on(
      "postgres_changes",
      {
        event: "*",
        schema: "public",
        table: "shopping_items",
        filter: `group_id=eq.${groupId}`,
      },
      onPayload
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
}
