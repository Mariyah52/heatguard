// Cloudflare Worker for heatguard.imadi.tech
// Serves the HeatGuard app (hosted on Render) under the imadi.tech domain.
const ORIGIN = "heatguard-6756.onrender.com";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    url.protocol = "https:";
    url.hostname = ORIGIN;
    url.port = "";
    return fetch(new Request(url, request));
  },
};
