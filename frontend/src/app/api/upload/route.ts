import { route, type Router } from '@better-upload/server';
import { toRouteHandler } from '@better-upload/server/adapters/next';
import { aws } from '@better-upload/server/clients';

const router: Router = {
  // Using dummy AWS credentials since no S3 bucket is configured yet.
  client: aws({
    accessKeyId: process.env.AWS_ACCESS_KEY_ID || 'dummy',
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || 'dummy',
    region: process.env.AWS_REGION || 'us-east-1',
  }),
  bucketName: process.env.S3_BUCKET_NAME || 'dummy-bucket',
  routes: {
    inbox: route({
      fileTypes: ['image/*', 'application/pdf'],
      maxFileSize: 10485760,
    }),
  },
};

export const { POST } = toRouteHandler(router);
