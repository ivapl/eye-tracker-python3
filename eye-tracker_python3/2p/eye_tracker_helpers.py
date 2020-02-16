from video_handling import *
from geometry_helpers import *


# CONTOUR FUNCTIONS #


def contourCentre(contour):
    moments = cv2.moments(contour)
    if moments["m00"] != 0:
        c = moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]
    else:
        if len(contour) == 1:
            c = tuple(contour.squeeze().tolist())
        else:
            points = contour.squeeze().tolist()
            c = findMidpoint(*points)
    return c


def contourAngle(contour):
    if len(contour) == 1:
        return
    else:
        moments = cv2.moments(contour)
        mu20 = moments["mu20"] / moments["m00"]
        mu02 = moments["mu02"] / moments["m00"]
        mu11 = moments["mu11"] / moments["m00"]
        if (mu20-mu02) != 0:
            theta = 0.5 * math.atan(2*mu11/(mu20-mu02))
        else:
            theta = math.pi / 2
        return theta


def findSwimBladder(contours):
    cs = [contourCentre(cnt) for cnt in contours]
    ds = [distance(p1, p2) for p1, p2 in zip([cs[0], cs[0], cs[1]], [cs[1], cs[2], cs[2]])]
    shortest_i = ds.index(min(ds))
    sb_i = 2-shortest_i
    return sb_i


def findAllContours(image, thresh):
    #image = cv2.medianBlur(image, 11)
    white = np.full(image.shape, 255, dtype='uint8')
    inverted = white-image
    threshed = applyThreshold(inverted, thresh, 'binary')
    contours = findContours(threshed)
    internals = contours[:3]
    return internals


# ADJUST THRESHOLDS #


def getThreshold(video, winname, thresh_name, start_val):
    try:
        disp = video.getDisplay(winname)
        threshval = disp.trackbars['thresholds'][thresh_name]
    except ValueError:
        threshval = start_val
    return threshval


def displayThreshold(image, **kwargs):
    if kwargs['roi'] is not None:
        img = cropImage(image, kwargs['roi'])
    else:
        img = image
    thresh = getThreshold(kwargs['video'], kwargs['winname'], kwargs['thresh_name'], kwargs['start_val'])
    internals = findAllContours(img, thresh=thresh)
    # sb_i = findSwimBladder(internals)
    # internals.pop(sb_i)
    outline = drawContours(img, internals, c=255)
    return outline


def setThreshold(video, initial, roi):

    winname = 'press enter to set new threshold'
    thresh_name = 'thresh'

    displayKwargs = dict(video=video, winname=winname, thresh_name=thresh_name, start_val=initial, roi=roi)

    video.addDisplay(winname, displayFunction=displayThreshold, displayKwargs=displayKwargs)
    video.addThreshbar(winname, thresh_name, initial)
    k = cv2.waitKey(0)

    if k == enter_key:
        thresh = getThreshold(video, winname, thresh_name, 'not used')
        video.removeDisplay(winname)
        return thresh
    else:
        return initial


# ANALYSIS FUNCTIONS #
# FROM TOMMY ---------
def mod2pi(angle):
    return angle % (np.pi * 2)


def abs_angle_diff(a, b):
    angle = abs(mod2pi(a) - mod2pi(b))
    if np.pi * 2 - angle < angle:
        return np.pi * 2 - angle
    return angle


def longAxisAngle(contour, heading):
    if len(contour) == 1:
        return
    moments = cv2.moments(contour)
    m00 = moments["m00"]
    m10 = moments["m10"]
    m01 = moments["m01"]
    m11 = moments["m11"]
    m02 = moments["m02"]
    m20 = moments['m20']

    x = m10 / m00
    y = m01 / m00

    a = m20 / m00 - x ** 2
    b = 2 * (m11 / m00 - x * y)
    c = m02 / m00 - y ** 2

    theta = 0.5 * np.arctan(b / (a - c)) + (a < c) * np.pi / 2
    theta_1 = mod2pi(theta + np.pi)
    if abs_angle_diff(theta_1, heading) < abs_angle_diff(theta, heading):
        return theta_1
    return theta
# FROM TOMMY -------
'''

def longAxisAngle(contour, theta):
    phi = contourAngle(contour) # POSITIVE ANGLES ARE CCW IN IMAGE
    v1 = angle2vector(phi)
    v2 = np.array([-v1[1], v1[0]]) # ROTATED 90 DEGREES MORE CCW

    vectors = [v1, v2]

    vx, vy, x0, y0 = cv2.fitLine(contour, distType=cv2.cv.CV_DIST_L2, param=0, reps=0.01, aeps=0.01)
    vc = np.array([vx, vy]).squeeze()

    dot_products = [abs(np.dot(vc, v)) for v in vectors]
    i = dot_products.index(max(dot_products)) # INDEX OF VECTOR PARALLEL WITH LONG AXIS
    # IF ORTHOGONAL VECTOR PARALLEL WITH LONG AXIS, ROTATE PHI 90 DEGREES MORE CCW
    if i == 1:
        phi += math.pi / 2

    vf = angle2vector(theta)
    dot_sign = np.sign(np.dot(vectors[i], vf)) # ORIENTATION OF EYE VECTOR RELATIVE TO BODY AXIS
    # IF SIGN IS NEGATIVE, EYE VECTOR IS OBTUSE WITH BODY AXIS: ROTATE PHI 180 DEGREES
    if dot_sign == -1:
        phi += math.pi

    return phi % (2 * math.pi)
'''


def frameData(image, thresh):
    contours = findAllContours(image, thresh=thresh)
    sb_i = findSwimBladder(contours)
    sb = contours.pop(sb_i)
    c = contourCentre(sb)

    eye_cs = [contourCentre(eye) for eye in contours]
    eye_c_xs, eye_c_ys = zip(*eye_cs)
    mp = findMidpoint(*eye_cs)

    orientation = angleAB(c, mp) # POSITIVE ANGLES ARE CCW IN IMAGE

    # FOR A CCW ROTATION OF THE BODY AXIS
    if math.pi / 4 <= orientation < 3 * math.pi / 4:
        # DOWN
        left_i = eye_c_xs.index(max(eye_c_xs))
    elif 3 * math.pi / 4 <= orientation < 5 * math.pi / 4:
        # LEFT
        left_i = eye_c_ys.index(max(eye_c_ys))
    elif 5 * math.pi / 4 <= orientation < 7 * math.pi / 4:
        # UP
        left_i = eye_c_xs.index(min(eye_c_xs))
    else:
        # RIGHT
        left_i = eye_c_ys.index(min(eye_c_ys))

    eye_l = contours.pop(left_i)
    eye_l_c = eye_cs.pop(left_i)
    eye_l_th = longAxisAngle(eye_l, orientation)

    eye_r = contours.pop()
    eye_r_c = eye_cs.pop()
    eye_r_th = longAxisAngle(eye_r, orientation)

    return c, orientation, eye_l_c, eye_l_th, eye_r_c, eye_r_th


# CHECK TRACKING HELPERS #


def drawCCWRotation(image, p, angle, size, color):
    v = angle2vector(angle)
    v *= size
    p1 = (int(round(p[0])), int(round(p[1])))
    p2 = (int(round(p[0] + v[0])), int(round(p[1] + v[1])))
    cv2.line(image, p1, p2, color=color)
    cv2.circle(image, p1, 3, color, -1)


def showEyes(image, thresh, roi):

    if roi is not None:
        img = cropImage(image, roi)
    else:
        img = image

    c, th, l_c, l_phi, r_c, r_phi = frameData(img, thresh)

    show = cv2.cvtColor(img, cv2.cv.CV_GRAY2BGR)
    blue = (255, 0, 0)
    green = (0, 255, 0)

    drawCCWRotation(show, l_c, l_phi, 50, blue)
    drawCCWRotation(show, r_c, r_phi, 50, green)

    return show


