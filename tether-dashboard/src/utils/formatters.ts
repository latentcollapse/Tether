export function formatTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

export function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toISOString().split('T')[0];
}

export function truncateHandle(handle: string): string {
  if (!handle) return '';
  if (handle.length <= 15) return handle;
  
  // E.g., h&l_messages_9cf1e6bf5ecd...
  const prefix = handle.substring(0, 15); // h&l_messages_...
  const firstChars = handle.substring(15, 27); // 12 chars of hash
  
  // The exact logic requested: h&l_{table}_{12-char prefix}
  // This assumes the handle already starts with the table designator.
  // Actually, we'll just format it smartly to fit the requirement
  const parts = handle.split('_');
  if (parts.length >= 3) {
      const type = parts[0];
      const table = parts[1];
      const hash = parts.slice(2).join('_');
      return `${type}_${table}_${hash.substring(0, 12)}...`;
  }
  
  return `${handle.substring(0, 15)}...`;
}

export function timeAgo(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  
  if (seconds < 60) return `${Math.max(1, seconds)} seconds ago`;
  
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minutes ago`;
  
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hours ago`;
  
  const days = Math.floor(hours / 24);
  return `${days} days ago`;
}
