import { loader } from 'fumadocs-core/source';
import { openapi } from './openapi';

export const apiSource = loader(
  {
    openapi: await openapi.staticSource({
      baseDir: '',
      meta: { folderStyle: 'separator' },
      per: 'tag',
    }),
  },
  {
    baseUrl: '/docs/api',
    icon: (name) => name,
    plugins: [openapi.loaderPlugin()],
  },
);
