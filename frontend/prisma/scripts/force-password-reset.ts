/**
 * One-off, standalone script: sets `must_reset_password = true` for every
 * existing row in `users`. Idempotent and safe to re-run.
 *
 * This is deliberately NOT wired into any app code path or npm script that
 * runs automatically — per the implementation plan (rollout order step 3),
 * actually running this for real is a decision deferred until S2 (auth) is
 * built and verified. As of S1, the `users` table is empty anyway (fresh
 * schema, no legacy rows yet), so running it today is a no-op — this script
 * exists now so it's ready once real user rows exist.
 *
 * Usage:
 *   npx tsx prisma/scripts/force-password-reset.ts --dry-run   # count only, no writes
 *   npx tsx prisma/scripts/force-password-reset.ts             # actually apply
 */
import { PrismaClient } from "#@/generated/prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";

async function main() {
  const dryRun = process.argv.includes("--dry-run");

  const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL });
  const prisma = new PrismaClient({ adapter });

  try {
    const affectedCount = await prisma.user.count({
      where: { mustResetPassword: false },
    });
    const totalCount = await prisma.user.count();

    if (dryRun) {
      console.log(
        `[dry-run] ${totalCount} user row(s) total; ${affectedCount} would be updated ` +
          `(mustResetPassword: false -> true). No writes performed.`,
      );
      return;
    }

    const result = await prisma.user.updateMany({
      where: { mustResetPassword: false },
      data: { mustResetPassword: true },
    });
    console.log(
      `Updated ${result.count} of ${totalCount} user row(s): mustResetPassword set to true.`,
    );
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((err) => {
  console.error("force-password-reset failed:", err);
  process.exitCode = 1;
});
