/** Nonces are generated in proxy and forwarded to Next's dynamic renderer. */
export function contentSecurityPolicy(nonce:string, development=false) {
  if(!/^[A-Za-z0-9+/=]+$/.test(nonce)) throw new Error('Invalid nonce');
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development?" 'unsafe-eval'":''}`,
    "script-src-attr 'none'",
    // React uses inline style attributes; scripts never receive unsafe-inline.
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob:",
    `connect-src 'self'${development?' ws://localhost:3000 ws://127.0.0.1:3000':''}`,
    "object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'",
  ].join('; ');
}
