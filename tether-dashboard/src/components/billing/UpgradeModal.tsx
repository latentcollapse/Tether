import { useEffect } from 'react';
import { X } from 'lucide-react';
import { useSubscriptionStore } from '../../store/subscriptionStore';
import { getUpgradePlans, openExternalUrl } from '../../utils/subscription';

export function UpgradeModal() {
  const isOpen = useSubscriptionStore((state) => state.isUpgradeModalOpen);
  const closeUpgradeModal = useSubscriptionStore((state) => state.closeUpgradeModal);
  const plans = getUpgradePlans();

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeUpgradeModal();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [closeUpgradeModal, isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="absolute inset-0 z-30 flex items-center justify-center bg-[#05060a]/80 px-4 backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          closeUpgradeModal();
        }
      }}
    >
      <div className="w-full max-w-5xl rounded-xl border border-[#ffffff14] bg-[#0f111a] shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-[#ffffff14] px-6 py-5">
          <div>
            <h2 className="text-xl font-semibold text-white">Upgrade Tether</h2>
            <p className="mt-1 text-sm text-[#8892b0]">Choose the hosted path that fits your node count and delivery model.</p>
          </div>
          <button
            type="button"
            onClick={closeUpgradeModal}
            className="rounded-lg border border-[#ffffff14] bg-[#05060a] p-2 text-[#8892b0] transition-colors hover:text-white"
            aria-label="Close upgrade modal"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4 px-6 py-6 md:grid-cols-3">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className="flex h-full flex-col justify-between rounded-xl border border-[#ffffff14] bg-[#05060a] p-5"
            >
              <div>
                <div className="text-sm font-semibold uppercase tracking-wide text-[#00f2ff]">{plan.name}</div>
                <div className="mt-2 text-2xl font-semibold text-white">{plan.price}</div>
                <p className="mt-3 text-sm leading-6 text-[#8892b0]">{plan.description}</p>
              </div>

              <div className="mt-6">
                <button
                  type="button"
                  disabled={!plan.ctaUrl}
                  onClick={() => {
                    if (plan.ctaUrl) {
                      openExternalUrl(plan.ctaUrl);
                    }
                  }}
                  className={`w-full rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
                    plan.ctaUrl
                      ? 'bg-[#00f2ff] text-[#05060a] hover:bg-[#6cf7ff]'
                      : 'cursor-not-allowed border border-[#ffffff14] bg-[#ffffff0d] text-[#8892b0]'
                  }`}
                >
                  {plan.ctaUrl ? 'Get Access' : 'Coming soon'}
                </button>
                <p className="mt-3 text-xs text-[#8892b0]">You&apos;ll be redirected to Stripe. Nothing is stored on our servers.</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
