// Kept free of astro:content so node --test can import it.

const host = (url: string): string => {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, '');
  } catch {
    return '';
  }
};

/**
 * The gig's own page on the venue's website, from the pages the scraper read it from. Only a page
 * on the venue's own host counts, so ticket sellers and promoters are skipped, and a bare homepage
 * (Limelight's feed has no per-event pages) doesn't count either.
 */
export function venueEventUrl(sources: { url?: string }[], website: string | undefined): string | undefined {
  const venueHost = website ? host(website) : '';
  if (!venueHost) return undefined;
  return sources.find(({ url }) => url && host(url) === venueHost && new URL(url).pathname.replace(/\/+$/, '') !== '')?.url;
}
