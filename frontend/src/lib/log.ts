const isProd = process.env.NODE_ENV === "production";

export const log = {
  error(message: any, ...rest: unknown[]) {
    if (isProd) return;
    // eslint-disable-next-line no-console
    console.error(message, ...rest);
  },
  warn(message: any, ...rest: unknown[]) {
    if (isProd) return;
    // eslint-disable-next-line no-console
    console.warn(message, ...rest);
  },
  info(message: any, ...rest: unknown[]) {
    if (isProd) return;
    // eslint-disable-next-line no-console
    console.info(message, ...rest);
  },
};
