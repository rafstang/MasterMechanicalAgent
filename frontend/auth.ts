import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

export const { handlers, auth, signIn, signOut } = NextAuth({
  // Explicit secret so Cloud Run / Docker always resolve (also accept v4-style NEXTAUTH_SECRET).
  secret: process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET,
  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID,
      clientSecret: process.env.AUTH_GOOGLE_SECRET,
    }),
  ],
  callbacks: {
    jwt({ token, user, account, profile }) {
      // Persist Google profile on the JWT so `auth()` in Route Handlers gets email/name (not only id).
      if (user) {
        if (user.email) token.email = user.email;
        if (user.name) token.name = user.name;
      }
      if (account && profile && typeof profile === "object") {
        const p = profile as { email?: string | null; name?: string | null };
        if (p.email) token.email = p.email;
        if (p.name) token.name = p.name;
      }
      return token;
    },
    session({ session, token }) {
      if (session.user) {
        if (token.sub) session.user.id = token.sub;
        if (typeof token.email === "string") session.user.email = token.email;
        if (typeof token.name === "string") session.user.name = token.name;
      }
      return session;
    },
  },
  trustHost: true,
});
