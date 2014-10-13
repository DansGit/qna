import sys
import random
import time

class ProgressBar(object):
    def __init__(self, total, width=48, mark='='):
        self.total = total
        self.intervals = []
        self.ticks = 0
        self.estimate = 'HH:MM:SS - HH:MM:SS'
        self.start_time = None
        self.width = width
        self.mark = mark

        # Float from 0 to 1.
        # Larger means narrower
        # time range, but is less
        # likely to be accurate.
        self.sample_size = .8

    def start(self):
        self.start_time = time.time()
        self._show()

    def has_started(self):
        if self.start_time is None:
            return False
        else:
            return True

    def tick(self):
        if self.start_time is None:
            print "ERROR: ProgressBar not started."

        self.ticks += 1
        if len(self.intervals) > 0:
            self.intervals.append(time.time() - (self.start_time + sum(self.intervals)))
        else:
            self.intervals.append(time.time() - self.start_time)
        self._monte_carlo() # Update estimate

        # Display the updated bar
        self._show()

    def is_done(self):
        return self.ticks == self.total


    def _show(self):
        filled_space = _scale(self.ticks, self.total, self.width)

        sys.stdout.write("\r{estimate} [{marks}{spaces}] {percent}% ({ticks}/{total})".format(
                estimate=self.estimate,
                marks=self.mark * filled_space,
                spaces=' ' * (self.width - filled_space),
                percent=round((self.ticks / float(self.total)) * 100, 2),
                ticks=self.ticks,
                total=self.total
                ))
        if self.ticks == self.total:
            sys.stdout.write('\nTotal time: {}\n'.format(
                format_time(time.time() - self.start_time)))
        sys.stdout.flush()

    def _monte_carlo(self):
        """Generates a time estimate using the monte carlo method.
        This method computes a range of estimates based on randomally
        select sample from intervals. It then returns a probable range
        between two times (i.e 30 to 40 minutes) in which the process is likely
        to finish. While less percise, it is much more likely to be accurate.
        """
        N = 16 # Number of estimates to generate

        if not len(self.intervals) > 2:
            return

        estimates = []

        for x in range(N):
            # Choose random intervals from our interval list
            sample = [random.choice(self.intervals) \
                    for x in range(int(round(len(
                        self.intervals) * self.sample_size)))]

            # Generate an estimate based on the sample average.
            avg = sum(sample) / float(len(sample))
            estimates.append(avg * (self.total - self.ticks))

        estimates.sort()

        # We arbitralily choose the estimates at the 4
        # and 12 positions to represent our upper and
        # lower bounds of our time estimate.
        lower_bound = estimates[4]
        upper_bound = estimates[12]

        self.estimate = "{lower} - {upper}".format(
                lower=format_time(lower_bound),
                upper=format_time(upper_bound)
                )


def _scale(n, mx1, mx2):
    """Scales a proportion n out of mx1 to new proportion whose max value
    is mx2.
    """
    return (n * mx2) / mx1


def format_time(secs):
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    return  "%02d:%02d:%02d" % (h, m, s)


if __name__ == '__main__':
    pbar = progressbar(10)
    for i in range(10):
        time.sleep(3)
        pbar.update()
