import { Paper, Stack, Typography } from '@mui/material';
import { motion } from 'framer-motion';

interface MetricCardProps {
  title: string;
  value: string;
  subValue?: string;
}

export function MetricCard({ title, value, subValue }: MetricCardProps) {
  return (
    <Paper
      component={motion.div}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      sx={{ p: 2.5, minHeight: 122 }}
    >
      <Stack spacing={0.6}>
        <Typography variant="caption" color="text.secondary">
          {title}
        </Typography>
        <Typography variant="h5">{value}</Typography>
        {subValue ? (
          <Typography variant="body2" color="success.light">
            {subValue}
          </Typography>
        ) : null}
      </Stack>
    </Paper>
  );
}
