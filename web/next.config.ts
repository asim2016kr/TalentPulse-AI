import type { NextConfig } from 'next';
const config: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{source:'/:path*',headers:[
      {key:'X-Frame-Options',value:'DENY'},
      {key:'X-Content-Type-Options',value:'nosniff'},
      {key:'Referrer-Policy',value:'no-referrer'},
      {key:'Permissions-Policy',value:'camera=(), microphone=(), geolocation=()'},
      {key:'Content-Security-Policy',value:"frame-ancestors 'none'; base-uri 'self'; object-src 'none'"}
    ]},{ source: '/api/:path*', headers: [
      {key:'X-Content-Type-Options',value:'nosniff'},
      {key:'Cache-Control',value:'no-store'},
      {key:'Referrer-Policy',value:'strict-origin-when-cross-origin'}
    ]}];
  }
};
export default config;
