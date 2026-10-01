/** Remove only the local bubble belonging to a failed request. */
export function removeMessageById(messages, id) {
  return messages.filter((message) => message.id !== id)
}
